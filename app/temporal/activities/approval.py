"""
Activity de Approval - Criação e gerenciamento de aprovações.
"""
import logging
import secrets
from datetime import datetime, timedelta
from typing import Dict, Any, List
from temporalio import activity

logger = logging.getLogger(__name__)


@activity.defn
async def create_approval(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Cria aprovação para revisão humana.
    
    Args:
        data: {
            execution_id,
            node: {id, config, ...},
            workflow_id,
            organization_id,
            generated_documents: [{document_id, file_url, pdf_url, ...}],
            source_data
        }
    
    Returns:
        {
            approval_id,
            approval_token,
            expires_at: datetime ISO string
        }
    """
    from app.database import db
    from app.models import WorkflowApproval, WorkflowExecution
    from flask import current_app
    
    node = data['node']
    config = node.get('config', {})
    execution_id = data['execution_id']
    
    activity.logger.info(f"Criando approval para execução {execution_id}")
    
    with current_app.app_context():
        execution = WorkflowExecution.query.get(execution_id)
        if not execution:
            raise ValueError(f'Execução não encontrada: {execution_id}')
        
        # Configurações do node
        approver_emails = config.get('approver_emails', [])
        message_template = config.get('message_template', 'Por favor, revise os documentos gerados.')
        timeout_hours = config.get('timeout_hours', 48)
        auto_approve_on_timeout = config.get('auto_approve_on_timeout', False)
        
        if not approver_emails:
            raise ValueError('approver_emails não configurado no node de aprovação')
        
        # Coletar URLs dos documentos
        document_urls = []
        for doc_info in data.get('generated_documents', []):
            doc_url = {
                'document_id': doc_info.get('document_id'),
                'name': doc_info.get('name', 'Documento'),
            }
            if doc_info.get('pdf_url'):
                doc_url['url'] = doc_info['pdf_url']
            elif doc_info.get('file_url'):
                doc_url['url'] = doc_info['file_url']
            document_urls.append(doc_url)
        
        # Calcular expiração
        expires_at = datetime.utcnow() + timedelta(hours=timeout_hours)
        
        # Snapshot do context para retomada
        execution_context = {
            'source_object_id': data.get('source_object_id'),
            'source_object_type': data.get('source_object_type'),
            'source_data': data.get('source_data', {}),
            'generated_documents': data.get('generated_documents', []),
            'metadata': {
                'current_node_position': node.get('position', 0)
            }
        }
        
        # Criar aprovações (uma por aprovador)
        approvals = []
        for approver_email in approver_emails:
            approval = WorkflowApproval(
                workflow_execution_id=execution.id,
                workflow_id=data['workflow_id'],
                node_id=node['id'],
                execution_context=execution_context,
                approver_email=approver_email,
                approval_token=secrets.token_urlsafe(32),
                status='pending',
                message_template=message_template,
                timeout_hours=timeout_hours,
                auto_approve_on_timeout=auto_approve_on_timeout,
                document_urls=document_urls,
                expires_at=expires_at
            )
            db.session.add(approval)
            approvals.append(approval)
        
        db.session.commit()
        
        activity.logger.info(f"Criadas {len(approvals)} aprovações para execução {execution_id}")
        
        # Retornar dados da primeira aprovação (principal)
        main_approval = approvals[0]
        
        return {
            'approval_id': str(main_approval.id),
            'approval_token': main_approval.approval_token,
            'expires_at': expires_at.isoformat(),
            'approval_ids': [str(a.id) for a in approvals],
            'approver_emails': approver_emails
        }


@activity.defn
async def expire_approval(approval_id: str) -> bool:
    """
    Marca aprovação como expirada.
    
    Args:
        approval_id: ID da aprovação
    
    Returns:
        True se expirou, False se já estava decidida
    """
    from app.database import db
    from app.models import WorkflowApproval
    from flask import current_app
    
    with current_app.app_context():
        approval = WorkflowApproval.query.get(approval_id)
        if not approval:
            raise ValueError(f'Aprovação não encontrada: {approval_id}')
        
        # Se já foi decidida, não expirar
        if approval.status in ['approved', 'rejected', 'expired']:
            activity.logger.info(f"Aprovação {approval_id} já está {approval.status}")
            return False
        
        # Verificar se deve auto-aprovar
        if approval.auto_approve_on_timeout:
            approval.status = 'approved'
            approval.approved_at = datetime.utcnow()
            activity.logger.info(f"Aprovação {approval_id} auto-aprovada por timeout")
        else:
            approval.status = 'expired'
            activity.logger.info(f"Aprovação {approval_id} expirada")
        
        db.session.commit()
        return True

