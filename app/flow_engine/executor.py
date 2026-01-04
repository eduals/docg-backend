"""
Flow Executor - Main orchestrator for flow execution

Responsibilities:
- Load flow definition and version
- Execute trigger
- Iterate through steps
- Handle branching
- Track execution state
- Create FlowRun record
- Log execution
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from uuid import uuid4, UUID
import asyncio

from app.database import db
from app.models.flow import Flow, FlowVersion, FlowRun, FlowRunLog, FlowRunStatus
from app.flow_engine.variable_resolver import VariableResolver
from app.flow_engine.step_processor import StepProcessor
from app.flow_engine.branching import BranchingHandler
from app.flow_engine.loop_handler import LoopHandler

logger = logging.getLogger(__name__)


class FlowExecutor:
    """
    Main executor for Activepieces-style flows.

    Usage:
        executor = FlowExecutor()
        run_id = await executor.execute(
            flow_id='uuid',
            trigger_data={'deal_id': '123'},
            project_id='uuid'
        )
    """

    def __init__(self):
        self.step_processor = StepProcessor()

    async def execute(
        self,
        flow_id: str,
        trigger_data: Optional[Dict[str, Any]] = None,
        project_id: Optional[str] = None,
    ) -> str:
        """
        Execute a flow.

        Args:
            flow_id: Flow UUID
            trigger_data: Data to pass to trigger (e.g., webhook payload)
            project_id: Project ID (if not set in flow)

        Returns:
            FlowRun UUID

        Raises:
            ValueError: If flow not found or not enabled
        """
        # 1. Load flow
        flow = db.session.get(Flow, flow_id)
        if not flow:
            raise ValueError(f"Flow not found: {flow_id}")

        if flow.status != 'ENABLED':
            raise ValueError(f"Flow is not enabled: {flow.status}")

        # Get published version
        if not flow.published_version_id:
            raise ValueError("Flow has no published version")

        version = db.session.get(FlowVersion, flow.published_version_id)
        if not version:
            raise ValueError(f"Published version not found: {flow.published_version_id}")

        if version.state != 'LOCKED':
            raise ValueError(f"Published version is not locked: {version.state}")

        # Use flow's project_id if not provided
        if not project_id:
            project_id = str(flow.project_id)

        # 2. Create FlowRun
        run = FlowRun(
            id=uuid4(),
            flow_id=UUID(flow_id),
            flow_version_id=version.id,
            status=FlowRunStatus.QUEUED,
            started_at=datetime.utcnow(),
            trigger_data=trigger_data or {},
            progress=0,
        )
        db.session.add(run)
        db.session.commit()

        run_id = str(run.id)
        logger.info(f"Created FlowRun: {run_id} for flow: {flow.name}")

        try:
            # 3. Execute flow
            await self._execute_flow(run, version, project_id)

            # 4. Mark as completed
            run.status = FlowRunStatus.COMPLETED
            run.completed_at = datetime.utcnow()
            run.progress = 100
            db.session.commit()

            logger.info(f"FlowRun completed: {run_id}")
            return run_id

        except Exception as e:
            # Mark as failed
            run.status = FlowRunStatus.FAILED
            run.completed_at = datetime.utcnow()
            run.error_message = str(e)
            db.session.commit()

            logger.error(f"FlowRun failed: {run_id} - {e}")
            self._log(run.id, 'error', 'execution', f"Flow execution failed: {e}")

            raise

    async def _execute_flow(
        self,
        run: FlowRun,
        version: FlowVersion,
        project_id: str
    ):
        """
        Execute flow steps.

        Args:
            run: FlowRun instance
            version: FlowVersion instance
            project_id: Project ID
        """
        # Update status
        run.status = FlowRunStatus.RUNNING
        db.session.commit()

        # Parse flow definition
        definition = version.definition
        trigger_def = version.trigger

        if not trigger_def:
            raise ValueError("Flow has no trigger defined")

        # 1. Execute trigger
        self._log(run.id, 'info', 'trigger', f"Executing trigger: {trigger_def.get('piece_name')}")

        trigger_success, trigger_output, trigger_error = await self._execute_trigger(
            trigger_def,
            run.trigger_data,
            project_id
        )

        if not trigger_success:
            raise RuntimeError(f"Trigger failed: {trigger_error}")

        self._log(run.id, 'ok', 'trigger', "Trigger executed successfully")

        # 2. Initialize variable resolver
        resolver = VariableResolver(
            trigger_output=trigger_output or {},
            steps_output={}
        )

        # 3. Execute steps
        steps = definition.get('steps', [])
        total_steps = len(steps)

        for idx, step_def in enumerate(steps):
            step_name = step_def.get('name', f'step_{idx}')
            step_type = step_def.get('type')

            # Update progress
            progress = int(((idx + 1) / (total_steps + 1)) * 100)
            run.progress = progress
            run.current_step = {
                'index': idx,
                'name': step_name,
                'type': step_type
            }
            db.session.commit()

            self._log(run.id, 'info', 'step', f"Executing step {idx + 1}/{total_steps}: {step_name}")

            # Execute step based on type
            if step_type == 'ACTION':
                success, output, error = await self._execute_action_step(
                    step_def,
                    resolver,
                    project_id
                )
            elif step_type == 'BRANCH':
                success, output, error = await self._execute_branch_step(
                    run.id,
                    step_def,
                    resolver,
                    project_id
                )
            elif step_type == 'LOOP':
                success, output, error = await self._execute_loop_step(
                    run.id,
                    step_def,
                    resolver,
                    project_id
                )
            else:
                success, output, error = False, None, f"Unknown step type: {step_type}"

            # Check result
            if not success:
                self._log(run.id, 'error', 'step', f"Step failed: {step_name} - {error}")
                raise RuntimeError(f"Step {step_name} failed: {error}")

            # Add step output to resolver
            if output:
                resolver.add_step_output(step_name, output)

            self._log(run.id, 'ok', 'step', f"Step completed: {step_name}")

        self._log(run.id, 'ok', 'execution', "Flow execution completed successfully")

    async def _execute_trigger(
        self,
        trigger_def: Dict[str, Any],
        trigger_data: Dict[str, Any],
        project_id: str
    ) -> tuple:
        """
        Execute trigger step.

        Args:
            trigger_def: Trigger definition
            trigger_data: Input data for trigger
            project_id: Project ID

        Returns:
            Tuple of (success, output, error)
        """
        piece_name = trigger_def.get('piece_name')
        trigger_name = trigger_def.get('trigger_name')
        settings = trigger_def.get('settings', {})
        connection_id = trigger_def.get('connection_id')

        # For webhook triggers, use trigger_data as output directly
        if piece_name == 'webhook':
            return True, trigger_data, None

        # For other triggers, execute handler
        return await self.step_processor.process_trigger(
            piece_name=piece_name,
            trigger_name=trigger_name,
            input_params=settings,
            project_id=project_id,
            connection_id=connection_id
        )

    async def _execute_action_step(
        self,
        step_def: Dict[str, Any],
        resolver: VariableResolver,
        project_id: str
    ) -> tuple:
        """
        Execute action step.

        Args:
            step_def: Step definition
            resolver: Variable resolver
            project_id: Project ID

        Returns:
            Tuple of (success, output, error)
        """
        step_name = step_def.get('name')
        piece_name = step_def.get('piece_name')
        action_name = step_def.get('action_name')
        settings = step_def.get('settings', {})
        connection_id = step_def.get('connection_id')

        return await self.step_processor.process_action(
            step_name=step_name,
            piece_name=piece_name,
            action_name=action_name,
            input_params=settings,
            resolver=resolver,
            project_id=project_id,
            connection_id=connection_id
        )

    async def _execute_branch_step(
        self,
        run_id: UUID,
        step_def: Dict[str, Any],
        resolver: VariableResolver,
        project_id: str
    ) -> tuple:
        """
        Execute branch step.

        Args:
            run_id: FlowRun ID
            step_def: Branch step definition
            resolver: Variable resolver
            project_id: Project ID

        Returns:
            Tuple of (success, output, error)
        """
        step_name = step_def.get('name')
        branching_handler = BranchingHandler(resolver)

        # Evaluate which branch to take
        branch_name = branching_handler.evaluate_branch(step_def)

        if not branch_name:
            self._log(run_id, 'warn', 'branch', f"No matching branch in {step_name}")
            return True, {'branch_taken': None}, None

        self._log(run_id, 'info', 'branch', f"Taking branch: {branch_name}")

        # Get steps for selected branch
        branch_steps = branching_handler.get_branch_steps(step_def, branch_name)

        # Execute branch steps
        branch_results = []
        for branch_step in branch_steps:
            step_type = branch_step.get('type')

            if step_type == 'ACTION':
                success, output, error = await self._execute_action_step(
                    branch_step,
                    resolver,
                    project_id
                )

                if not success:
                    return False, None, error

                if output:
                    branch_step_name = branch_step.get('name')
                    resolver.add_step_output(branch_step_name, output)
                    branch_results.append(output)

        return True, {'branch_taken': branch_name, 'results': branch_results}, None

    async def _execute_loop_step(
        self,
        run_id: UUID,
        step_def: Dict[str, Any],
        resolver: VariableResolver,
        project_id: str
    ) -> tuple:
        """
        Execute loop step.

        Args:
            run_id: FlowRun ID
            step_def: Loop step definition
            resolver: Variable resolver
            project_id: Project ID

        Returns:
            Tuple of (success, output, error)
        """
        step_name = step_def.get('name')
        loop_handler = LoopHandler(resolver)

        # Get items to iterate
        items = loop_handler.get_loop_items(step_def)

        if not items:
            self._log(run_id, 'warn', 'loop', f"No items to iterate in {step_name}")
            return True, {'iterations': 0, 'results': []}, None

        self._log(run_id, 'info', 'loop', f"Starting loop with {len(items)} items")

        # Get loop steps
        loop_steps = step_def.get('steps', [])
        iteration_results = []

        # Iterate over items
        for idx, item in enumerate(items):
            # Create item context
            item_context = loop_handler.create_item_context(step_def, item, idx)

            # Create temporary resolver with item context
            # This allows {{item.field}} references
            temp_resolver = VariableResolver(
                trigger_output=resolver.trigger_output,
                steps_output={**resolver.steps_output, **item_context}
            )

            # Execute loop steps for this iteration
            iteration_output = {}
            for loop_step in loop_steps:
                step_type = loop_step.get('type')

                if step_type == 'ACTION':
                    success, output, error = await self._execute_action_step(
                        loop_step,
                        temp_resolver,
                        project_id
                    )

                    if not success:
                        self._log(run_id, 'error', 'loop', f"Loop iteration {idx} failed: {error}")
                        return False, None, error

                    if output:
                        iteration_output.update(output)

            iteration_results.append(iteration_output)

        # Process results
        loop_output = loop_handler.process_loop_results(iteration_results)
        self._log(run_id, 'ok', 'loop', f"Loop completed: {len(items)} iterations")

        return True, loop_output, None

    def _log(
        self,
        run_id: UUID,
        level: str,
        domain: str,
        message: str
    ):
        """
        Create execution log.

        Args:
            run_id: FlowRun ID
            level: Log level (ok, info, warn, error)
            domain: Domain (trigger, step, execution, etc)
            message: Log message
        """
        log = FlowRunLog(
            id=uuid4(),
            flow_run_id=run_id,
            timestamp=datetime.utcnow(),
            level=level,
            domain=domain,
            message=message,
        )
        db.session.add(log)
        db.session.commit()


class FlowExecutionError(Exception):
    """Custom exception for flow execution errors"""
    pass
