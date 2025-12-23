"""
Activate Workflow Controller.
"""

from flask import jsonify, g
from app.database import db
from app.models import Workflow, WorkflowNode
from .helpers import workflow_to_dict


def activate_workflow(workflow_id: str):
    """Ativa um workflow (valida nodes antes)"""
    workflow = Workflow.query.filter_by(
        id=workflow_id,
        organization_id=g.organization_id
    ).first_or_404()

    # Buscar nodes
    nodes = WorkflowNode.query.filter_by(
        workflow_id=workflow.id
    ).order_by(WorkflowNode.position).all()

    # Validar que existe trigger node
    trigger_node = next((n for n in nodes if n.is_trigger()), None)
    if not trigger_node:
        return jsonify({'error': 'Workflow deve ter um trigger node (hubspot, webhook ou google-forms)'}), 400

    # Validar que trigger está configurado
    if not trigger_node.is_configured():
        return jsonify({'error': 'Trigger node não está configurado'}), 400

    # Validar que todos os nodes obrigatórios estão configurados
    unconfigured_nodes = [n for n in nodes if not n.is_configured() and not n.is_trigger()]
    if unconfigured_nodes:
        return jsonify({
            'error': f'{len(unconfigured_nodes)} node(s) não estão configurados',
            'unconfigured_nodes': [str(n.id) for n in unconfigured_nodes]
        }), 400

    # Validar cadeia de nodes (sem gaps)
    positions = sorted([n.position for n in nodes])
    expected_positions = list(range(1, len(nodes) + 1))
    if positions != expected_positions:
        return jsonify({
            'error': 'Cadeia de nodes incompleta. Existem gaps nas posições.'
        }), 400

    workflow.status = 'active'
    db.session.commit()

    return jsonify({
        'success': True,
        'workflow': workflow_to_dict(workflow)
    })
