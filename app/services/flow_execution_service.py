"""
Flow Execution Service - Service to start flow executions via Temporal

Provides high-level API to execute flows asynchronously.
"""

import logging
import asyncio
from typing import Dict, Any, Optional
from datetime import timedelta
from uuid import uuid4

from temporalio.client import Client
from app.temporal.config import get_config

logger = logging.getLogger(__name__)


class FlowExecutionService:
    """
    Service to execute flows via Temporal workflows.

    Usage:
        service = FlowExecutionService()
        workflow_id = await service.start_flow_execution(
            flow_id='uuid',
            trigger_data={'deal_id': '123'},
            project_id='uuid'
        )
    """

    def __init__(self, temporal_client: Optional[Client] = None):
        """
        Initialize service.

        Args:
            temporal_client: Optional Temporal client (will be created if not provided)
        """
        self.temporal_client = temporal_client
        self.config = get_config()

    async def get_client(self) -> Client:
        """
        Get or create Temporal client.

        Returns:
            Temporal client
        """
        if not self.temporal_client:
            self.temporal_client = await Client.connect(
                self.config.address,
                namespace=self.config.namespace
            )
        return self.temporal_client

    async def start_flow_execution(
        self,
        flow_id: str,
        trigger_data: Optional[Dict[str, Any]] = None,
        project_id: Optional[str] = None,
    ) -> str:
        """
        Start flow execution via Temporal workflow.

        Args:
            flow_id: Flow UUID
            trigger_data: Trigger input data
            project_id: Project ID

        Returns:
            Workflow ID
        """
        from app.temporal.workflows.flow_workflow import FlowWorkflow

        logger.info(f"Starting flow execution for flow: {flow_id}")

        # Get client
        client = await self.get_client()

        # Generate workflow ID
        workflow_id = f"flow-{flow_id}-{uuid4()}"

        # Start workflow
        handle = await client.start_workflow(
            FlowWorkflow.run,
            args=[flow_id, trigger_data, project_id],
            id=workflow_id,
            task_queue=self.config.task_queue,
            execution_timeout=timedelta(hours=1),
        )

        logger.info(f"Started workflow: {workflow_id}")

        return workflow_id

    async def cancel_flow_execution(self, workflow_id: str):
        """
        Cancel a running flow execution.

        Args:
            workflow_id: Workflow ID to cancel
        """
        logger.info(f"Cancelling workflow: {workflow_id}")

        client = await self.get_client()

        # Get workflow handle
        handle = client.get_workflow_handle(workflow_id)

        # Send cancel signal
        await handle.signal("cancel")

        logger.info(f"Cancel signal sent to workflow: {workflow_id}")

    async def pause_flow_execution(self, workflow_id: str):
        """
        Pause a running flow execution.

        Args:
            workflow_id: Workflow ID to pause
        """
        logger.info(f"Pausing workflow: {workflow_id}")

        client = await self.get_client()

        # Get workflow handle
        handle = client.get_workflow_handle(workflow_id)

        # Send pause signal
        await handle.signal("pause")

        logger.info(f"Pause signal sent to workflow: {workflow_id}")

    async def get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
        """
        Get workflow execution status.

        Args:
            workflow_id: Workflow ID

        Returns:
            Workflow status info
        """
        client = await self.get_client()

        # Get workflow handle
        handle = client.get_workflow_handle(workflow_id)

        # Describe workflow
        description = await handle.describe()

        return {
            "workflow_id": workflow_id,
            "status": description.status.name,
            "start_time": description.start_time.isoformat() if description.start_time else None,
            "execution_time": str(description.execution_time) if description.execution_time else None,
        }

    async def wait_for_completion(
        self,
        workflow_id: str,
        timeout: Optional[timedelta] = None
    ) -> Dict[str, Any]:
        """
        Wait for workflow to complete and get result.

        Args:
            workflow_id: Workflow ID
            timeout: Optional timeout

        Returns:
            Workflow result
        """
        client = await self.get_client()

        # Get workflow handle
        handle = client.get_workflow_handle(workflow_id)

        # Wait for result
        if timeout:
            result = await asyncio.wait_for(handle.result(), timeout=timeout.total_seconds())
        else:
            result = await handle.result()

        return result


# Global instance
_service_instance = None


def get_flow_execution_service() -> FlowExecutionService:
    """
    Get singleton instance of FlowExecutionService.

    Returns:
        FlowExecutionService instance
    """
    global _service_instance
    if _service_instance is None:
        _service_instance = FlowExecutionService()
    return _service_instance
