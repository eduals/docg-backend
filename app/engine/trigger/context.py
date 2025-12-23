"""
Trigger Context Builder - Constrói contexto para trigger steps.
"""

from typing import Dict, Any, Optional
from app.engine.global_variable import GlobalVariable, AuthContext, FlowContext, StepContext, ExecutionContext


async def build_trigger_context(
    node: Any,
    execution_id: str,
    flow_context: Any,
    trigger_data: Dict[str, Any] = None,
) -> GlobalVariable:
    """
    Constrói GlobalVariable context para um trigger.

    Args:
        node: WorkflowNode trigger
        execution_id: ID da execução
        flow_context: FlowContextData
        trigger_data: Dados do trigger (webhook payload, etc)

    Returns:
        GlobalVariable configurado
    """
    from app.models import DataSourceConnection, WorkflowExecution

    # Construir AuthContext
    auth = AuthContext()
    connection_id = None

    if node.config:
        connection_id = node.config.get('source_connection_id')

    if connection_id:
        connection = DataSourceConnection.query.get(connection_id)
        if connection:
            credentials = connection.get_credentials()
            auth = AuthContext(
                connection_id=str(connection.id),
                auth_type=connection.source_type,
                credentials=credentials,
                access_token=credentials.get('access_token'),
                refresh_token=credentials.get('refresh_token'),
            )

    # Construir FlowContext
    flow = FlowContext(
        workflow_id=flow_context.workflow_id,
        workflow_name=flow_context.workflow_name,
        organization_id=flow_context.organization_id,
        status=flow_context.status,
        trigger_type=flow_context.trigger_type,
        trigger_config=flow_context.trigger_config,
        nodes=flow_context.nodes,
    )

    # Construir StepContext
    step = StepContext(
        step_id=str(node.id),
        step_type=node.node_type,
        position=node.position,
        app_key=node.node_type,
        parameters=trigger_data or {},
        config=node.config or {},
    )

    # Construir ExecutionContext
    execution = WorkflowExecution.query.get(execution_id)
    exec_context = ExecutionContext(
        execution_id=execution_id,
        started_at=execution.started_at.isoformat() if execution and execution.started_at else None,
        status=execution.status if execution else 'running',
        trigger_data=trigger_data or {},
    )

    return GlobalVariable(
        auth=auth,
        flow=flow,
        step=step,
        execution=exec_context,
        trigger_output={},  # Será preenchido após execução
        action_output={},
        previous_steps=[],
    )
