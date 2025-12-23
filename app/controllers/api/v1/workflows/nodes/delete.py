"""
Delete Workflow Node Controller.
"""

from flask import jsonify, g
from app.database import db
from app.models import Workflow, WorkflowNode


def delete_workflow_node(workflow_id: str, node_id: str):
    """Deleta um node do workflow"""
    workflow = Workflow.query.filter_by(
        id=workflow_id,
        organization_id=g.organization_id
    ).first_or_404()

    node = WorkflowNode.query.filter_by(
        id=node_id,
        workflow_id=workflow.id
    ).first_or_404()

    # Não permitir deletar trigger node
    if node.is_trigger():
        return jsonify({
            'error': 'Não é possível deletar o trigger node'
        }), 400

    # Verificar se há nodes filhos
    children = WorkflowNode.query.filter_by(
        parent_node_id=node.id
    ).count()

    if children > 0:
        return jsonify({
            'error': f'Não é possível deletar node com {children} node(s) filho(s). Remova os nodes filhos primeiro.'
        }), 400

    db.session.delete(node)
    db.session.commit()

    return jsonify({'success': True})
