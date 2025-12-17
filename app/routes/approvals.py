"""
Rotas para aprovações de workflow (Human-in-the-Loop).
"""
from flask import Blueprint, request, jsonify, g
from app.database import db
from app.models import WorkflowApproval, WorkflowExecution, Workflow
from app.services.workflow_executor import WorkflowExecutor
from app.utils.auth import require_auth, require_org
import logging
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)
approvals_bp = Blueprint('approvals', __name__, url_prefix='/api/v1/approvals')


@approvals_bp.route('/<approval_token>', methods=['GET'])
def get_approval_status(approval_token):
    """
    Retorna status de uma aprovação (público, não requer auth).
    """
    approval = WorkflowApproval.query.filter_by(approval_token=approval_token).first_or_404()
    
    return jsonify({
        'success': True,
        'approval': approval.to_dict()
    })


@approvals_bp.route('/<approval_token>/approve', methods=['POST'])
def approve_workflow(approval_token):
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
            # === TEMPORAL: Enviar signal ===
            execution = WorkflowExecution.query.get(approval.workflow_execution_id)
            if execution and execution.temporal_workflow_id:
                send_approval_decision(
                    workflow_execution_id=str(approval.workflow_execution_id),
                    approval_id=str(approval.id),
                    decision='approved'
                )
                logger.info(f"Signal de aprovação enviado para execução {approval.workflow_execution_id}")
            else:
                # Fallback: usar método síncrono
                from app.services.approval_service import resume_workflow_execution
                resume_workflow_execution(approval)
        else:
            # Temporal não habilitado: usar método síncrono
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


@approvals_bp.route('/<approval_token>/reject', methods=['POST'])
def reject_workflow(approval_token):
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
                # === TEMPORAL: Enviar signal de rejeição ===
                send_approval_decision(
                    workflow_execution_id=str(approval.workflow_execution_id),
                    approval_id=str(approval.id),
                    decision='rejected'
                )
                logger.info(f"Signal de rejeição enviado para execução {approval.workflow_execution_id}")
            else:
                # Fallback: marcar direto no banco
                execution.status = 'failed'
                execution.error_message = f'Workflow rejeitado: {rejection_comment or "Sem comentário"}'
                db.session.commit()
        except Exception as e:
            logger.exception(f'Erro ao enviar signal de rejeição: {str(e)}')
            # Fallback
            execution.status = 'failed'
            execution.error_message = f'Workflow rejeitado: {rejection_comment or "Sem comentário"}'
            db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Workflow rejeitado'
    })


@approvals_bp.route('/workflows/<workflow_id>', methods=['GET'])
@require_auth
@require_org
def list_workflow_approvals(workflow_id):
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

