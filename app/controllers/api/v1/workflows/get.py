"""
Get Workflow Controller.
"""

from flask import request, jsonify, g
from app.models import Workflow, WorkflowNode
from .helpers import workflow_to_dict


def get_workflow(workflow_id: str):
    """Retorna detalhes de um workflow"""
    workflow = Workflow.query.filter_by(
        id=workflow_id,
        organization_id=g.organization_id
    ).first_or_404()

    include_nodes = request.args.get('include_nodes', 'false').lower() == 'true'
    include_mappings = request.args.get('include_mappings', 'false').lower() == 'true'
    include_ai_mappings = request.args.get('include_ai_mappings', 'false').lower() == 'true'

    result = workflow_to_dict(workflow, include_mappings=include_mappings, include_ai_mappings=include_ai_mappings)

    if include_nodes:
        nodes = WorkflowNode.query.filter_by(
            workflow_id=workflow.id
        ).order_by(WorkflowNode.position).all()
        result['nodes'] = [node.to_dict(include_config=True) for node in nodes]

    return jsonify(result)
