"""
Update Workflow Node Controller.
"""

from flask import request, jsonify, g
from app.database import db
from app.models import Workflow, WorkflowNode
from app.models.workflow import TRIGGER_NODE_TYPES


def update_workflow_node(workflow_id: str, node_id: str):
    """Atualiza um node do workflow"""
    workflow = Workflow.query.filter_by(
        id=workflow_id,
        organization_id=g.organization_id
    ).first_or_404()

    node = WorkflowNode.query.filter_by(
        id=node_id,
        workflow_id=workflow.id
    ).first_or_404()

    data = request.get_json()

    # Não permitir alterar node_type de um trigger para não-trigger
    if node.is_trigger() and 'node_type' in data and data['node_type'] not in TRIGGER_NODE_TYPES:
        return jsonify({
            'error': 'Não é possível alterar o tipo do trigger node para um tipo não-trigger'
        }), 400

    # Atualizar campos permitidos
    if 'position' in data:
        if data['position'] == 1 and not node.is_trigger():
            return jsonify({
                'error': 'Apenas trigger nodes (hubspot, webhook, google-forms) podem ter position=1'
            }), 400
        node.position = data['position']

    if 'parent_node_id' in data:
        parent_node_id = data['parent_node_id']
        if parent_node_id:
            parent = WorkflowNode.query.filter_by(
                id=parent_node_id,
                workflow_id=workflow.id
            ).first()
            if not parent:
                return jsonify({'error': 'parent_node_id não encontrado'}), 400
        node.parent_node_id = parent_node_id

    if 'config' in data:
        node.config = data['config']
        if node.is_configured():
            node.status = 'configured'
        else:
            node.status = 'draft'

    if 'status' in data:
        node.status = data['status']

    db.session.commit()

    return jsonify({
        'success': True,
        'node': node.to_dict(include_config=True)
    })


def update_workflow_node_config(workflow_id: str, node_id: str):
    """
    Atualiza configuração de um node.

    Body:
    {
        "config": {
            "template_id": "uuid",
            "output_name_template": "...",
            ...
        }
    }
    """
    workflow = Workflow.query.filter_by(
        id=workflow_id,
        organization_id=g.organization_id
    ).first_or_404()

    node = WorkflowNode.query.filter_by(
        id=node_id,
        workflow_id=workflow.id
    ).first_or_404()

    data = request.get_json()

    if 'config' not in data:
        return jsonify({'error': 'config é obrigatório'}), 400

    node.config = data['config']

    if node.is_configured():
        node.status = 'configured'
    else:
        node.status = 'draft'

    db.session.commit()

    return jsonify({
        'success': True,
        'config': node.config,
        'status': node.status
    })
