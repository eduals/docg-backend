"""
List Workflows Controller.
"""

from flask import request, jsonify, g
from app.models import Workflow, WorkflowNode
from .helpers import workflow_to_dict


def list_workflows():
    """Lista workflows da organização"""
    org_id = g.organization_id
    status = request.args.get('status')
    object_type = request.args.get('object_type')

    query = Workflow.query.filter_by(organization_id=org_id)

    if status:
        query = query.filter_by(status=status)

    workflows = query.order_by(Workflow.updated_at.desc()).all()

    # Se object_type foi fornecido, filtrar workflows que têm trigger node configurado para esse tipo
    if object_type:
        filtered_workflows = []
        for w in workflows:
            trigger_node = WorkflowNode.query.filter_by(
                workflow_id=w.id,
                node_type='trigger'
            ).first()
            if trigger_node and trigger_node.config:
                trigger_config = trigger_node.config or {}
                if trigger_config.get('source_object_type') == object_type:
                    filtered_workflows.append(w)
        workflows = filtered_workflows

    result = []
    for w in workflows:
        workflow_dict = workflow_to_dict(w)
        # Adicionar contagem de nodes
        nodes_count = WorkflowNode.query.filter_by(workflow_id=w.id).count()
        nodes_configured = WorkflowNode.query.filter_by(
            workflow_id=w.id,
            status='configured'
        ).count()
        workflow_dict['nodes_count'] = nodes_count
        workflow_dict['nodes_configured'] = nodes_configured
        result.append(workflow_dict)

    return jsonify({
        'workflows': result
    })
