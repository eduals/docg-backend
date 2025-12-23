"""
Reject Workflow Controller.
"""

from flask import request, jsonify
from app.database import db
from app.models import WorkflowApproval, WorkflowExecution
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def reject_workflow(approval_token: str):
    """
    Rejeita um workflow (público, não requer auth).
    """
    data = request.get_json() or {}
    rejection_comment = data.get('comment', '')

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
    approval.status = 'rejected'
    approval.rejected_at = datetime.utcnow()
    approval.rejection_comment = rejection_comment
    db.session.commit()

    # Marcar execução como failed ou enviar signal
    execution = WorkflowExecution.query.get(approval.workflow_execution_id)
    if execution:
        try:
            from app.temporal.service import send_approval_decision, is_temporal_enabled

            if is_temporal_enabled() and execution.temporal_workflow_id:
                send_approval_decision(
                    workflow_execution_id=str(approval.workflow_execution_id),
                    approval_id=str(approval.id),
                    decision='rejected'
                )
                logger.info(f"Signal de rejeição enviado para execução {approval.workflow_execution_id}")
            else:
                execution.status = 'failed'
                execution.error_message = f'Workflow rejeitado: {rejection_comment or "Sem comentário"}'
                db.session.commit()
        except Exception as e:
            logger.exception(f'Erro ao enviar signal de rejeição: {str(e)}')
            execution.status = 'failed'
            execution.error_message = f'Workflow rejeitado: {rejection_comment or "Sem comentário"}'
            db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Workflow rejeitado'
    })
