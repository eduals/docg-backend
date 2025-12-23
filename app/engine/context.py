"""
ExecutionContext Builder.

Constrói o objeto ExecutionContext ($) para execução de actions e triggers.
Similar ao global-variable.js do Automatisch.
"""

from typing import Dict, Any, Optional, List
import httpx
import logging

from app.apps.base import (
    ExecutionContext,
    AuthContext,
    AppContext,
    FlowContext,
    StepContext,
    ExecutionMetadata,
    TriggerOutput,
    ActionOutput,
    Datastore,
)

logger = logging.getLogger(__name__)


async def build_execution_context(
    # App info
    app_key: str,
    app_name: str,
    app_base_url: Optional[str] = None,

    # Flow info
    workflow_id: str = None,
    workflow_name: str = None,
    organization_id: str = None,

    # Step info
    step_id: str = None,
    action_key: str = None,
    position: int = 0,
    parameters: Dict[str, Any] = None,

    # Execution info
    execution_id: str = None,
    test_run: bool = False,
    until_step: Optional[str] = None,

    # Auth info
    connection_id: str = None,
    credentials: Dict[str, Any] = None,

    # HTTP Client
    http_client: httpx.AsyncClient = None,

    # Previous steps
    previous_steps: List[Any] = None,
    trigger_output: Dict[str, Any] = None,

    # Webhook
    webhook_url: Optional[str] = None,
) -> ExecutionContext:
    """
    Constrói um ExecutionContext completo.

    Args:
        app_key: Chave do app (ex: 'hubspot')
        app_name: Nome do app (ex: 'HubSpot')
        app_base_url: URL base da API
        workflow_id: ID do workflow
        workflow_name: Nome do workflow
        organization_id: ID da organização
        step_id: ID do step atual
        action_key: Chave da action
        position: Posição do step no workflow
        parameters: Parâmetros JÁ COMPUTADOS (sem {{step.x.y}})
        execution_id: ID da execução
        test_run: Se é uma execução de teste
        until_step: Step até onde executar (para test runs)
        connection_id: ID da conexão
        credentials: Credenciais decriptografadas
        http_client: Cliente HTTP já configurado
        previous_steps: Lista de ExecutionSteps anteriores
        trigger_output: Output do trigger
        webhook_url: URL do webhook (se aplicável)

    Returns:
        ExecutionContext configurado
    """

    # Auth context
    auth = AuthContext(
        id=connection_id or '',
        data=credentials or {}
    )

    # App context
    app = AppContext(
        key=app_key,
        name=app_name,
        base_url=app_base_url
    )

    # Flow context
    flow = FlowContext(
        id=workflow_id or '',
        name=workflow_name or '',
        organization_id=organization_id or ''
    )

    # Step context
    step = StepContext(
        id=step_id or '',
        app_key=app_key,
        action_key=action_key or '',
        position=position,
        parameters=parameters or {}
    )

    # Execution metadata
    execution = ExecutionMetadata(
        id=execution_id or '',
        test_run=test_run,
        until_step=until_step
    )

    # Outputs
    trigger_out = TriggerOutput(data=[trigger_output] if trigger_output else [])
    action_out = ActionOutput(data=None)

    # Datastore
    datastore = Datastore(organization_id=organization_id or '')

    # HTTP client (criar se não fornecido)
    if http_client is None:
        http_client = httpx.AsyncClient(
            base_url=app_base_url,
            timeout=30.0
        )

    return ExecutionContext(
        auth=auth,
        app=app,
        flow=flow,
        step=step,
        execution=execution,
        http=http_client,
        trigger_output=trigger_out,
        action_output=action_out,
        datastore=datastore,
        webhook_url=webhook_url,
        _previous_steps=previous_steps or []
    )


async def build_context_from_execution(
    execution_step,
    workflow,
    workflow_node,
    app,
    http_client: httpx.AsyncClient,
    previous_steps: List[Any] = None,
    trigger_output: Dict[str, Any] = None,
    test_run: bool = False,
    until_step: str = None,
) -> ExecutionContext:
    """
    Constrói ExecutionContext a partir de objetos do banco.

    Args:
        execution_step: ExecutionStep atual
        workflow: Workflow
        workflow_node: WorkflowNode atual
        app: BaseApp instance
        http_client: Cliente HTTP configurado
        previous_steps: Steps anteriores
        trigger_output: Output do trigger
        test_run: Se é teste
        until_step: Step até onde executar

    Returns:
        ExecutionContext configurado
    """
    # Determinar action_key do node
    action_key = _get_action_key(workflow_node)

    # Obter connection_id e credentials
    connection_id = None
    credentials = {}

    if workflow_node.config:
        connection_id = workflow_node.config.get('connection_id')

    if connection_id:
        from app.models import DataSourceConnection
        connection = DataSourceConnection.query.get(connection_id)
        if connection:
            credentials = connection.get_credentials() or {}

    return await build_execution_context(
        # App
        app_key=app.key,
        app_name=app.name,
        app_base_url=app.base_url,

        # Flow
        workflow_id=str(workflow.id),
        workflow_name=workflow.name,
        organization_id=str(workflow.organization_id),

        # Step
        step_id=str(workflow_node.id),
        action_key=action_key,
        position=workflow_node.position,
        parameters=execution_step.data_in or {},

        # Execution
        execution_id=str(execution_step.execution_id),
        test_run=test_run,
        until_step=until_step,

        # Auth
        connection_id=connection_id,
        credentials=credentials,

        # HTTP
        http_client=http_client,

        # Context
        previous_steps=previous_steps,
        trigger_output=trigger_output,
    )


def _get_action_key(workflow_node) -> str:
    """Extrai action_key do node baseado no tipo e config."""
    node_type = workflow_node.node_type
    config = workflow_node.config or {}

    # Mapeamento de node_type para action_key
    mapping = {
        'trigger': config.get('trigger_type', 'manual'),
        'google-docs': config.get('action', 'copy-template'),
        'google-slides': config.get('action', 'copy-template'),
        'microsoft-word': config.get('action', 'copy-template'),
        'microsoft-powerpoint': config.get('action', 'copy-template'),
        'hubspot': config.get('action', 'get-object'),
        'gmail': config.get('action', 'send-email'),
        'outlook': config.get('action', 'send-email'),
        'clicksign': config.get('action', 'create-envelope'),
        'zapsign': config.get('action', 'create-document'),
        'webhook': 'send-request',
        'request-signatures': config.get('provider', 'clicksign'),
        'review-documents': 'review',
        'human-in-loop': 'approval',
    }

    return mapping.get(node_type, node_type)
