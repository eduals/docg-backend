"""
Flow Context Builder - Constrói contexto de workflow.

Similar ao buildFlowContext do Automatisch, carrega todas as informações
necessárias para executar um workflow.
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class FlowContextData:
    """Dados de contexto de um workflow."""
    workflow_id: str
    workflow_name: str
    organization_id: str
    status: str
    trigger_type: Optional[str] = None
    trigger_config: Optional[Dict[str, Any]] = None
    nodes: List[Dict[str, Any]] = field(default_factory=list)
    connections: Dict[str, Any] = field(default_factory=dict)
    templates: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'workflow_id': self.workflow_id,
            'workflow_name': self.workflow_name,
            'organization_id': self.organization_id,
            'status': self.status,
            'trigger_type': self.trigger_type,
            'trigger_config': self.trigger_config,
            'nodes': self.nodes,
            'connections': self.connections,
            'templates': self.templates,
        }


async def build_flow_context(workflow_id: str) -> FlowContextData:
    """
    Constrói o contexto completo de um workflow.

    Carrega:
    - Dados do workflow
    - Nodes do JSONB (normalizado para formato engine)
    - Connections associadas
    - Templates referenciados

    Args:
        workflow_id: ID do workflow

    Returns:
        FlowContextData com todos os dados
    """
    from app.models import Workflow, DataSourceConnection, Template
    from app.engine.flow.normalization import normalize_nodes_from_jsonb

    # Carregar workflow
    workflow = Workflow.query.get(workflow_id)
    if not workflow:
        raise ValueError(f"Workflow {workflow_id} not found")

    # Normalizar nodes do JSONB para formato engine
    nodes_data = normalize_nodes_from_jsonb(
        workflow.nodes or [],
        workflow.edges or []
    )

    connection_ids = set()
    template_ids = set()

    # Coletar IDs de connections e templates referenciados
    for node in nodes_data:
        config = node.get('config', {})
        if config:
            if 'connection_id' in config:
                connection_ids.add(config['connection_id'])
            if 'source_connection_id' in config:
                connection_ids.add(config['source_connection_id'])
            if 'template_id' in config:
                template_ids.add(config['template_id'])

    # Carregar connections
    connections = {}
    if connection_ids:
        for conn_id in connection_ids:
            if conn_id:
                conn = DataSourceConnection.query.get(conn_id)
                if conn:
                    connections[str(conn.id)] = {
                        'id': str(conn.id),
                        'source_type': conn.source_type,
                        'name': conn.name,
                        # Não incluir credentials por segurança
                    }

    # Carregar templates
    templates = {}
    if template_ids:
        for tmpl_id in template_ids:
            if tmpl_id:
                tmpl = Template.query.get(tmpl_id)
                if tmpl:
                    templates[str(tmpl.id)] = {
                        'id': str(tmpl.id),
                        'name': tmpl.name,
                        'file_type': tmpl.google_file_type,
                        'source_type': tmpl.source_type,
                    }

    # Determinar trigger type e config do primeiro node
    trigger_type = None
    trigger_config = None
    if nodes_data and nodes_data[0]:
        first_node = nodes_data[0]
        trigger_type = first_node.get('node_type')
        trigger_config = first_node.get('config', {})

    return FlowContextData(
        workflow_id=str(workflow.id),
        workflow_name=workflow.name,
        organization_id=str(workflow.organization_id),
        status=workflow.status,
        trigger_type=trigger_type,
        trigger_config=trigger_config,
        nodes=nodes_data,
        connections=connections,
        templates=templates,
    )


def get_trigger_node(flow_context: FlowContextData) -> Optional[Dict[str, Any]]:
    """
    Obtém o node de trigger do contexto.

    Args:
        flow_context: Contexto do workflow

    Returns:
        Dict do trigger node ou None
    """
    if flow_context.nodes:
        first_node = flow_context.nodes[0]
        if first_node.get('position') == 1:
            return first_node
    return None


def get_action_nodes(flow_context: FlowContextData) -> List[Dict[str, Any]]:
    """
    Obtém os nodes de action (position > 1).

    Args:
        flow_context: Contexto do workflow

    Returns:
        Lista de nodes de action ordenados
    """
    return [
        node for node in flow_context.nodes
        if node.get('position', 0) > 1
    ]


def get_node_by_id(flow_context: FlowContextData, node_id: str) -> Optional[Dict[str, Any]]:
    """
    Obtém um node específico pelo ID.

    Args:
        flow_context: Contexto do workflow
        node_id: ID do node

    Returns:
        Dict do node ou None
    """
    for node in flow_context.nodes:
        if node.get('id') == node_id:
            return node
    return None


def get_connection(flow_context: FlowContextData, connection_id: str) -> Optional[Dict[str, Any]]:
    """
    Obtém dados de uma connection.

    Args:
        flow_context: Contexto do workflow
        connection_id: ID da connection

    Returns:
        Dict da connection ou None
    """
    return flow_context.connections.get(connection_id)


def get_template(flow_context: FlowContextData, template_id: str) -> Optional[Dict[str, Any]]:
    """
    Obtém dados de um template.

    Args:
        flow_context: Contexto do workflow
        template_id: ID do template

    Returns:
        Dict do template ou None
    """
    return flow_context.templates.get(template_id)


def get_first_action_node(flow_context: FlowContextData) -> Optional[Dict[str, Any]]:
    """
    Obtém o primeiro node de action (position = 2).

    Args:
        flow_context: Contexto do workflow

    Returns:
        Dict do primeiro action node ou None
    """
    action_nodes = get_action_nodes(flow_context)
    return action_nodes[0] if action_nodes else None


def get_next_sequential_node(
    flow_context: FlowContextData,
    current_node_id: str
) -> Optional[Dict[str, Any]]:
    """
    Obtém o próximo node sequencial (por position).

    Args:
        flow_context: Contexto do workflow
        current_node_id: ID do node atual

    Returns:
        Dict do próximo node ou None se for o último
    """
    current_node = get_node_by_id(flow_context, current_node_id)
    if not current_node:
        return None

    current_position = current_node.get('position', 0)

    # Buscar node com position = current + 1
    for node in flow_context.nodes:
        if node.get('position') == current_position + 1:
            return node

    return None


def get_next_node(
    flow_context: FlowContextData,
    current_node_id: str,
    context: dict = None,
    previous_steps: list = None
) -> Optional[Dict[str, Any]]:
    """
    Determina o próximo node considerando branching.

    Se o node atual é um branch, avalia as condições.
    Caso contrário, retorna o próximo sequencial.

    Args:
        flow_context: Contexto do workflow
        current_node_id: ID do node atual
        context: Contexto da execução (para variáveis)
        previous_steps: Steps anteriores

    Returns:
        Dict do próximo node ou None
    """
    from app.engine.flow.branching import is_branch_node, evaluate_branch_conditions

    # Buscar node no flow_context
    current_node = get_node_by_id(flow_context, current_node_id)
    if not current_node:
        return None

    # Se é branch, avaliar condições
    if is_branch_node(current_node):
        next_node_id = evaluate_branch_conditions(
            current_node,
            context or {},
            previous_steps or []
        )
        if next_node_id:
            return get_node_by_id(flow_context, next_node_id)

    # Fallback: próximo sequencial
    return get_next_sequential_node(flow_context, current_node_id)
