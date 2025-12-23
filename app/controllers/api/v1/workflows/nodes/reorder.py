"""
Reorder Workflow Nodes Controller.
"""

from flask import request, jsonify, g, current_app
from app.database import db
from app.models import Workflow, WorkflowNode


def reorder_workflow_nodes(workflow_id: str):
    """
    Reordena nodes do workflow.

    Body:
    {
        "node_order": [
            {"node_id": "uuid1", "position": 1},
            {"node_id": "uuid2", "position": 2}
        ]
    }
    """
    workflow = Workflow.query.filter_by(
        id=workflow_id,
        organization_id=g.organization_id
    ).first_or_404()

    data = request.get_json()
    node_order = data.get('node_order', [])

    if not node_order:
        return jsonify({'error': 'node_order é obrigatório'}), 400

    # Validar que todos os nodes pertencem ao workflow
    node_ids = [item['node_id'] for item in node_order]
    nodes = WorkflowNode.query.filter(
        WorkflowNode.id.in_(node_ids),
        WorkflowNode.workflow_id == workflow.id
    ).all()

    if len(nodes) != len(node_ids):
        return jsonify({
            'error': 'Um ou mais nodes não pertencem a este workflow'
        }), 400

    # Validar que position 1 é um trigger
    position_1_node = next((item for item in node_order if item['position'] == 1), None)
    if position_1_node:
        node_1 = next((n for n in nodes if str(n.id) == position_1_node['node_id']), None)
        if not node_1 or not node_1.is_trigger():
            return jsonify({
                'error': 'O node na position 1 deve ser um trigger (hubspot, webhook ou google-forms)'
            }), 400

    # Atualizar positions em duas etapas
    try:
        # Etapa 1: Atualizar todos para posições temporárias (negativas)
        for idx, item in enumerate(node_order):
            node = next((n for n in nodes if str(n.id) == item['node_id']), None)
            if node:
                temp_position = -(idx + 1000)
                node.position = temp_position

        db.session.commit()

        # Etapa 2: Atualizar para posições finais
        for item in node_order:
            node = next((n for n in nodes if str(n.id) == item['node_id']), None)
            if node:
                node.position = item['position']

        db.session.commit()

        current_app.logger.info(f'Nodes reordenados com sucesso no workflow {workflow_id}')
        return jsonify({'success': True})

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Erro ao reordenar nodes no workflow {workflow_id}: {str(e)}')
        return jsonify({'error': f'Erro ao reordenar nodes: {str(e)}'}), 500
