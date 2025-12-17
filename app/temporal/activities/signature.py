"""
Activity de Signature - Envio para assinatura.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from temporalio import activity

logger = logging.getLogger(__name__)


@activity.defn
async def create_signature_request(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Cria request de assinatura.
    
    IDEMPOTÊNCIA: Verifica se já existe request para esta execução/node.
    
    Args:
        data: {
            execution_id,
            node: {id, config, ...},
            workflow_id,
            organization_id,
            generated_documents: [{document_id, file_id, pdf_file_id, ...}],
            source_data
        }
    
    Returns:
        {
            signature_request_id,
            external_id,
            external_url,
            expires_at: datetime ISO string (se houver)
        }
    """
    from app.database import db
    from app.models import SignatureRequest, GeneratedDocument, Workflow
    from app.services.integrations.signature.factory import SignatureProviderFactory
    from flask import current_app
    
    node = data['node']
    config = node.get('config', {})
    execution_id = data['execution_id']
    node_id = node['id']
    
    activity.logger.info(f"Criando signature request para execução {execution_id}")
    
    with current_app.app_context():
        # === IDEMPOTÊNCIA: Verificar se já existe ===
        existing = SignatureRequest.query.filter_by(
            workflow_execution_id=execution_id,
            node_id=node_id
        ).first()
        
        if existing:
            activity.logger.info(f"Signature request já existe: {existing.id}")
            return {
                'signature_request_id': str(existing.id),
                'external_id': existing.external_id,
                'external_url': existing.external_url,
                'expires_at': existing.expires_at.isoformat() if existing.expires_at else None,
                'reused': True
            }
        
        # Configurações
        provider = config.get('provider', 'clicksign')
        connection_id = config.get('connection_id')
        recipients = config.get('recipients', [])
        message = config.get('message')
        document_source = config.get('document_source', 'previous_node')
        expiration_days = config.get('expiration_days', 7)
        
        if not connection_id:
            raise ValueError('connection_id não configurado no node de assinatura')
        
        if not recipients:
            raise ValueError('recipients não configurado no node de assinatura')
        
        # Buscar documento
        document = _get_document(data, config, document_source)
        if not document:
            raise ValueError('Documento não encontrado para envio de assinatura')
        
        workflow = Workflow.query.get(data['workflow_id'])
        if not workflow:
            raise ValueError(f'Workflow não encontrado: {data["workflow_id"]}')
        
        # Obter adapter
        adapter = SignatureProviderFactory.get_adapter(
            provider=provider,
            connection_id=connection_id,
            organization_id=str(workflow.organization_id)
        )
        
        # Enviar para assinatura
        signature_request = adapter.send_document_for_signature(
            document=document,
            signers=recipients,
            message=message
        )
        
        # Adicionar campos de tracking
        signature_request.node_id = node_id
        signature_request.workflow_execution_id = execution_id
        
        # Calcular expiração
        expires_at = datetime.utcnow() + timedelta(days=expiration_days)
        signature_request.expires_at = expires_at
        
        # Inicializar signers_status
        signers_status = {}
        for signer in recipients:
            email = signer.get('email', '').lower()
            if email:
                signers_status[email] = 'pending'
        signature_request.signers_status = signers_status
        
        db.session.commit()
        
        activity.logger.info(
            f"Signature request criada: {signature_request.id} via {provider}"
        )
        
        return {
            'signature_request_id': str(signature_request.id),
            'external_id': signature_request.external_id,
            'external_url': signature_request.external_url,
            'expires_at': expires_at.isoformat(),
            'reused': False
        }


def _get_document(data: Dict, config: Dict, document_source: str) -> Optional['GeneratedDocument']:
    """
    Busca documento baseado na configuração do node.
    """
    from app.models import GeneratedDocument
    
    generated_documents = data.get('generated_documents', [])
    
    if document_source == 'previous_node':
        # Usar último documento com PDF
        if generated_documents:
            for doc_info in reversed(generated_documents):
                document_id = doc_info.get('document_id')
                if document_id:
                    document = GeneratedDocument.query.get(document_id)
                    if document and document.pdf_file_id:
                        return document
            
            # Se nenhum tem PDF, pegar o último
            last_doc = generated_documents[-1]
            document_id = last_doc.get('document_id')
            if document_id:
                return GeneratedDocument.query.get(document_id)
    
    elif document_source == 'specific_node':
        node_id = config.get('document_node_id')
        if node_id:
            for doc_info in generated_documents:
                if doc_info.get('node_id') == node_id:
                    document_id = doc_info.get('document_id')
                    if document_id:
                        return GeneratedDocument.query.get(document_id)
    
    elif document_source == 'specific_document':
        document_id = config.get('document_id')
        if document_id:
            return GeneratedDocument.query.get(document_id)
    
    return None


@activity.defn
async def expire_signature(signature_request_id: str) -> bool:
    """
    Marca signature request como expirada.
    
    Args:
        signature_request_id: ID da request
    
    Returns:
        True se expirou, False se já estava finalizada
    """
    from app.database import db
    from app.models import SignatureRequest
    from flask import current_app
    
    with current_app.app_context():
        sig_request = SignatureRequest.query.get(signature_request_id)
        if not sig_request:
            raise ValueError(f'SignatureRequest não encontrada: {signature_request_id}')
        
        # Se já foi finalizada, não expirar
        if sig_request.status in ['signed', 'declined', 'expired', 'error']:
            activity.logger.info(f"SignatureRequest {signature_request_id} já está {sig_request.status}")
            return False
        
        sig_request.status = 'expired'
        sig_request.completed_at = datetime.utcnow()
        db.session.commit()
        
        activity.logger.info(f"SignatureRequest {signature_request_id} expirada")
        return True

