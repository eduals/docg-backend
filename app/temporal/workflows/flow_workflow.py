"""
Flow Workflow - Temporal workflow for async flow execution

This workflow orchestrates the execution of Activepieces-style flows asynchronously.
"""

import asyncio
from datetime import timedelta
from typing import Dict, Any, Optional
from temporalio import workflow
from temporalio.common import RetryPolicy

# Import activities
with workflow.unsafe.imports_passed_through():
    from app.temporal.activities.flow_activities import (
        execute_flow_activity,
        update_flow_run_status_activity,
        log_flow_event_activity,
    )


@workflow.defn
class FlowWorkflow:
    """
    Temporal workflow for executing flows.

    Handles:
    - Async flow execution
    - Retries
    - Cancellation
    - Status updates
    """

    def __init__(self):
        self._cancel_requested = False
        self._pause_requested = False

    @workflow.run
    async def run(
        self,
        flow_id: str,
        trigger_data: Optional[Dict[str, Any]] = None,
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Run a flow workflow.

        Args:
            flow_id: Flow UUID
            trigger_data: Trigger input data
            project_id: Project ID

        Returns:
            Execution result
        """
        workflow.logger.info(f"Starting FlowWorkflow for flow: {flow_id}")

        # Define retry policy
        retry_policy = RetryPolicy(
            initial_interval=timedelta(seconds=1),
            maximum_interval=timedelta(seconds=10),
            maximum_attempts=3,
            non_retryable_error_types=["ValueError", "FlowExecutionError"],
        )

        try:
            # Execute flow via activity
            result = await workflow.execute_activity(
                execute_flow_activity,
                args=[flow_id, trigger_data, project_id],
                start_to_close_timeout=timedelta(minutes=30),
                retry_policy=retry_policy,
            )

            workflow.logger.info(f"FlowWorkflow completed for flow: {flow_id}")
            return result

        except Exception as e:
            workflow.logger.error(f"FlowWorkflow failed for flow {flow_id}: {e}")

            # Log failure
            await workflow.execute_activity(
                log_flow_event_activity,
                args=[
                    flow_id,
                    "error",
                    "workflow",
                    f"Workflow execution failed: {str(e)}",
                ],
                start_to_close_timeout=timedelta(seconds=30),
            )

            raise

    @workflow.signal
    async def cancel(self):
        """Signal to cancel the workflow."""
        workflow.logger.info("Cancel signal received")
        self._cancel_requested = True

    @workflow.signal
    async def pause(self):
        """Signal to pause the workflow."""
        workflow.logger.info("Pause signal received")
        self._pause_requested = True

    @workflow.query
    def is_cancelled(self) -> bool:
        """Query if workflow is cancelled."""
        return self._cancel_requested

    @workflow.query
    def is_paused(self) -> bool:
        """Query if workflow is paused."""
        return self._pause_requested
