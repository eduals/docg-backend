"""
Approve Workflow Controller.
"""

from flask import jsonify
from app.database import db
from app.models import WorkflowApproval, WorkflowExecution
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def approve_workflow(approval_token: str):
    """
    Aprova um workflow (público, não requer auth).
    """
    approval = WorkflowApproval.query.filter_by(approval_token=approval_token).first_or_404()

    if approval.status != 'pending':
        return jsonify({
            'error': f'Aprovação já foi {approval.status}'
        }), 400

    if approval.is_expired():
        approval.status = 'expired'
        db.session.commit()
        return jsonify({
            'error': 'Aprovação expirada'
        }), 400

    # Atualizar status
    approval.status = 'approved'
    approval.approved_at = datetime.utcnow()
    db.session.commit()

    # Retomar execução do workflow
    try:
        from app.temporal.service import send_approval_decision, is_temporal_enabled

        if is_temporal_enabled():
            execution = WorkflowExecution.query.get(approval.workflow_execution_id)
            if execution and execution.temporal_workflow_id:
                send_approval_decision(
                    workflow_execution_id=str(approval.workflow_execution_id),
                    approval_id=str(approval.id),
                    decision='approved'
                )
                logger.info(f"Signal de aprovação enviado para execução {approval.workflow_execution_id}")
            else:
                from app.services.approval_service import resume_workflow_execution
                resume_workflow_execution(approval)
        else:
            from app.services.approval_service import resume_workflow_execution
            resume_workflow_execution(approval)
    except Exception as e:
        logger.exception(f'Erro ao retomar execução: {str(e)}')
        return jsonify({
            'error': f'Erro ao retomar execução: {str(e)}'
        }), 500

    return jsonify({
        'success': True,
        'message': 'Workflow aprovado e execução retomada'
    })
