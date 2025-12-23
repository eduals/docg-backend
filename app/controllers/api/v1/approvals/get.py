"""
Get Approval Controller.
"""

from flask import jsonify
from app.models import WorkflowApproval


def get_approval_status(approval_token: str):
    """
    Retorna status de uma aprovação (público, não requer auth).
    """
    approval = WorkflowApproval.query.filter_by(approval_token=approval_token).first_or_404()

    return jsonify({
        'success': True,
        'approval': approval.to_dict()
    })
