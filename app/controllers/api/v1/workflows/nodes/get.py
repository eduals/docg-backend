"""
Get Workflow Node Controller.
"""

from flask import jsonify, g
from app.models import Workflow, WorkflowNode


def get_workflow_node(workflow_id: str, node_id: str):
    """Retorna detalhes de um node"""
    workflow = Workflow.query.filter_by(
        id=workflow_id,
        organization_id=g.organization_id
    ).first_or_404()

    node = WorkflowNode.query.filter_by(
        id=node_id,
        workflow_id=workflow.id
    ).first_or_404()

    return jsonify(node.to_dict(include_config=True))


def get_workflow_node_config(workflow_id: str, node_id: str):
    """Retorna configuração de um node"""
    workflow = Workflow.query.filter_by(
        id=workflow_id,
        organization_id=g.organization_id
    ).first_or_404()

    node = WorkflowNode.query.filter_by(
        id=node_id,
        workflow_id=workflow.id
    ).first_or_404()

    response_data = {
        'config': node.config or {},
        'status': node.status
    }

    # Adicionar webhook_token se for webhook trigger node
    if (node.node_type == 'webhook' or (node.node_type == 'trigger' and node.config.get('trigger_type') == 'webhook')) and node.webhook_token:
        response_data['webhook_token'] = node.webhook_token

    return jsonify(response_data)
