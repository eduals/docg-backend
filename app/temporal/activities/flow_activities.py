"""
Flow Activities - Temporal activities for flow execution

Activities are the actual execution logic called by workflows.
"""

import logging
from typing import Dict, Any, Optional
from temporalio import activity
from uuid import UUID

logger = logging.getLogger(__name__)


@activity.defn
async def execute_flow_activity(
    flow_id: str,
    trigger_data: Optional[Dict[str, Any]] = None,
    project_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Execute a flow.

    Args:
        flow_id: Flow UUID
        trigger_data: Trigger input data
        project_id: Project ID

    Returns:
        Execution result with run_id and status
    """
    # Import here to avoid circular dependencies
    from app.flow_engine import FlowExecutor

    logger.info(f"Executing flow activity for flow: {flow_id}")

    try:
        executor = FlowExecutor()
        run_id = await executor.execute(
            flow_id=flow_id,
            trigger_data=trigger_data,
            project_id=project_id,
        )

        logger.info(f"Flow executed successfully. Run ID: {run_id}")

        return {
            "success": True,
            "run_id": run_id,
            "status": "completed",
        }

    except Exception as e:
        logger.error(f"Flow execution failed: {e}")
        raise


@activity.defn
async def update_flow_run_status_activity(
    run_id: str,
    status: str,
    error_message: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Update flow run status.

    Args:
        run_id: FlowRun UUID
        status: New status
        error_message: Optional error message

    Returns:
        Updated run info
    """
    from app.database import db
    from app.models.flow import FlowRun, FlowRunStatus
    from datetime import datetime

    logger.info(f"Updating flow run {run_id} to status: {status}")

    try:
        # Query run
        run = db.session.get(FlowRun, UUID(run_id))
        if not run:
            raise ValueError(f"FlowRun not found: {run_id}")

        # Update status
        run.status = FlowRunStatus(status)

        if error_message:
            run.error_message = error_message

        if status in ['COMPLETED', 'FAILED', 'CANCELED']:
            run.completed_at = datetime.utcnow()
            run.progress = 100

        db.session.commit()

        logger.info(f"Flow run {run_id} updated to: {status}")

        return {
            "success": True,
            "run_id": run_id,
            "status": status,
        }

    except Exception as e:
        logger.error(f"Failed to update flow run: {e}")
        db.session.rollback()
        raise


@activity.defn
async def log_flow_event_activity(
    flow_id: str,
    level: str,
    domain: str,
    message: str,
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Log a flow event.

    Args:
        flow_id: Flow UUID
        level: Log level (ok, info, warn, error)
        domain: Domain (workflow, trigger, step, etc)
        message: Log message
        run_id: Optional FlowRun UUID

    Returns:
        Log info
    """
    from app.database import db
    from app.models.flow import FlowRunLog
    from datetime import datetime
    from uuid import uuid4

    logger.info(f"Logging flow event: {flow_id} - {level} - {message}")

    try:
        log = FlowRunLog(
            id=uuid4(),
            flow_run_id=UUID(run_id) if run_id else None,
            timestamp=datetime.utcnow(),
            level=level,
            domain=domain,
            message=message,
        )
        db.session.add(log)
        db.session.commit()

        return {
            "success": True,
            "log_id": str(log.id),
        }

    except Exception as e:
        logger.error(f"Failed to log event: {e}")
        db.session.rollback()
        raise


@activity.defn
async def get_flow_run_status_activity(run_id: str) -> Dict[str, Any]:
    """
    Get flow run status.

    Args:
        run_id: FlowRun UUID

    Returns:
        Run status info
    """
    from app.database import db
    from app.models.flow import FlowRun

    logger.info(f"Getting flow run status: {run_id}")

    try:
        run = db.session.get(FlowRun, UUID(run_id))
        if not run:
            raise ValueError(f"FlowRun not found: {run_id}")

        return {
            "success": True,
            "run_id": str(run.id),
            "status": run.status.value,
            "progress": run.progress,
            "current_step": run.current_step,
            "error_message": run.error_message,
        }

    except Exception as e:
        logger.error(f"Failed to get flow run status: {e}")
        raise
