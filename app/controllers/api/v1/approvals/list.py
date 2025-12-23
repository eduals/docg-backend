"""
List Workflow Approvals Controller.
"""

from flask import jsonify, g
from app.models import WorkflowApproval, Workflow


def list_workflow_approvals(workflow_id: str):
    """
    Lista todas as aprovações de um workflow (requer auth).
    """
    workflow = Workflow.query.filter_by(
        id=workflow_id,
        organization_id=g.organization_id
    ).first_or_404()

    approvals = WorkflowApproval.query.filter_by(workflow_id=workflow.id).order_by(
        WorkflowApproval.created_at.desc()
    ).all()

    return jsonify({
        'approvals': [approval.to_dict() for approval in approvals]
    })
