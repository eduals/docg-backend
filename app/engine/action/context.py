"""
Action Context Builder - Constrói contexto para action steps.
"""

from typing import Dict, Any, Optional, List
from app.engine.global_variable import GlobalVariable, AuthContext, FlowContext, StepContext, ExecutionContext, PreviousStepOutput


async def build_action_context(
    node: Any,
    execution_id: str,
    flow_context: Any,
    trigger_output: Dict[str, Any] = None,
    previous_steps: List[Any] = None,
) -> GlobalVariable:
    """
    Constrói GlobalVariable context para uma action.

    Args:
        node: WorkflowNode sendo executado
        execution_id: ID da execução
        flow_context: FlowContextData
        trigger_output: Output do trigger
        previous_steps: Lista de ExecutionSteps anteriores

    Returns:
        GlobalVariable configurado
    """
    from app.models import DataSourceConnection, WorkflowExecution

    # Construir AuthContext
    auth = AuthContext()
    connection_id = None

    if node.config:
        connection_id = node.config.get('connection_id') or node.config.get('source_connection_id')

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
                api_key=credentials.get('api_key'),
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
        app_key=_get_app_key_for_node(node.node_type),
        parameters=node.config or {},
        config=node.config or {},
    )

    # Construir ExecutionContext
    execution = WorkflowExecution.query.get(execution_id)
    exec_context = ExecutionContext(
        execution_id=execution_id,
        started_at=execution.started_at.isoformat() if execution and execution.started_at else None,
        status=execution.status if execution else 'running',
        trigger_data=execution.trigger_data if execution else {},
    )

    # Construir PreviousStepOutputs
    prev_outputs = []
    if previous_steps:
        for prev_step in previous_steps:
            if prev_step.status == 'success' and prev_step.data_out:
                prev_outputs.append(PreviousStepOutput(
                    step_id=str(prev_step.step_id),
                    step_type=prev_step.step_type,
                    position=prev_step.position,
                    data_out=prev_step.data_out,
                ))

    # Construir GlobalVariable
    return GlobalVariable(
        auth=auth,
        flow=flow,
        step=step,
        execution=exec_context,
        trigger_output=trigger_output or {},
        action_output={},  # Será preenchido após execução
        previous_steps=prev_outputs,
    )


def _get_app_key_for_node(node_type: str) -> str:
    """Mapeia node type para app key."""
    mapping = {
        'google-docs': 'google-docs',
        'google-slides': 'google-slides',
        'microsoft-word': 'microsoft-word',
        'microsoft-powerpoint': 'microsoft-powerpoint',
        'gmail': 'gmail',
        'outlook': 'outlook',
        'clicksign': 'clicksign',
        'request-signatures': 'clicksign',
        'zapsign': 'zapsign',
        'hubspot': 'hubspot',
    }
    return mapping.get(node_type, node_type)
