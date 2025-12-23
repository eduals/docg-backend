"""
List Workflow Nodes Controller.
"""

from flask import jsonify, g
from app.models import Workflow, WorkflowNode


def list_workflow_nodes(workflow_id: str):
    """Lista nodes de um workflow ordenados por position"""
    workflow = Workflow.query.filter_by(
        id=workflow_id,
        organization_id=g.organization_id
    ).first_or_404()

    nodes = WorkflowNode.query.filter_by(
        workflow_id=workflow.id
    ).order_by(WorkflowNode.position).all()

    return jsonify({
        'nodes': [node.to_dict(include_config=True) for node in nodes]
    })
