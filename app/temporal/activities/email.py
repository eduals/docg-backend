"""
Activity de Email - Envio de emails.
"""
import logging
from datetime import datetime
from typing import Dict, Any, List
from temporalio import activity

logger = logging.getLogger(__name__)


@activity.defn
async def execute_email_node(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa node de email.
    
    Suporta:
    - gmail: Gmail via SMTP
    - outlook: Outlook via Microsoft Graph API
    
    Args:
        data: {
            execution_id,
            node: {id, node_type, config, ...},
            workflow_id,
            organization_id,
            source_data,
            generated_documents
        }
    
    Returns:
        {success: bool, recipients: [...]}
    """
    from flask import current_app
    
    node = data['node']
    node_type = node.get('node_type')
    config = node.get('config', {})
    
    activity.logger.info(f"Executando email node {node['id']} tipo {node_type}")
    
    with current_app.app_context():
        if node_type == 'gmail':
            return await _send_gmail(data, config)
        elif node_type == 'outlook':
            return await _send_outlook(data, config)
        else:
            raise ValueError(f'Tipo de email não suportado: {node_type}')


async def _send_gmail(data: Dict[str, Any], config: Dict) -> Dict[str, Any]:
    """Envia email via Gmail SMTP"""
    from app.database import db
    from app.models import DataSourceConnection, GeneratedDocument, Workflow
    from app.services.email_service import EmailService
    from app.services.document_generation.tag_processor import TagProcessor
    
    connection_id = config.get('connection_id')
    if not connection_id:
        raise ValueError('connection_id não configurado no Gmail email node')
    
    workflow = Workflow.query.get(data['workflow_id'])
    if not workflow:
        raise ValueError(f'Workflow não encontrado: {data["workflow_id"]}')
    
    connection = DataSourceConnection.query.filter_by(
        id=connection_id,
        organization_id=workflow.organization_id,
        source_type='gmail_smtp'
    ).first()
    
    if not connection:
        raise ValueError(f'Conexão Gmail SMTP não encontrada: {connection_id}')
    
    credentials = connection.get_decrypted_credentials()
    smtp_host = credentials.get('smtp_host', 'smtp.gmail.com')
    smtp_port = credentials.get('smtp_port', 587)
    username = credentials.get('username')
    password = credentials.get('password')
    use_tls = credentials.get('use_tls', True)
    
    if not username or not password:
        raise ValueError('Credenciais SMTP incompletas')
    
    # Processar templates
    source_data = data.get('source_data', {})
    to_emails = config.get('to', [])
    subject_template = config.get('subject_template', '')
    body_template = config.get('body_template', '')
    body_type = config.get('body_type', 'html')
    
    to_processed = [TagProcessor.replace_tags(email, source_data) for email in to_emails]
    subject = TagProcessor.replace_tags(subject_template, source_data)
    body = TagProcessor.replace_tags(body_template, source_data)
    
    # Processar anexos
    attachments = _get_attachments(
        data, config, workflow.organization_id
    )
    
    # Enviar
    EmailService.send_via_smtp(
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        username=username,
        password=password,
        use_tls=use_tls,
        to=to_processed,
        subject=subject,
        body=body,
        body_type=body_type,
        cc=config.get('cc', []),
        bcc=config.get('bcc', []),
        attachments=attachments if attachments else None
    )
    
    activity.logger.info(f"Email Gmail enviado para {to_processed}")
    
    return {
        'success': True,
        'recipients': to_processed,
        'subject': subject
    }


async def _send_outlook(data: Dict[str, Any], config: Dict) -> Dict[str, Any]:
    """Envia email via Outlook (Microsoft Graph API)"""
    from app.database import db
    from app.models import DataSourceConnection, GeneratedDocument, Workflow
    from app.services.email_service import EmailService
    from app.services.document_generation.tag_processor import TagProcessor
    
    connection_id = config.get('connection_id')
    if not connection_id:
        raise ValueError('connection_id não configurado no Outlook email node')
    
    workflow = Workflow.query.get(data['workflow_id'])
    if not workflow:
        raise ValueError(f'Workflow não encontrado: {data["workflow_id"]}')
    
    connection = DataSourceConnection.query.filter_by(
        id=connection_id,
        organization_id=workflow.organization_id,
        source_type='microsoft'
    ).first()
    
    if not connection:
        raise ValueError(f'Conexão Microsoft não encontrada: {connection_id}')
    
    credentials = connection.get_decrypted_credentials()
    access_token = credentials.get('access_token')
    from_email = credentials.get('user_email')
    
    if not access_token or not from_email:
        raise ValueError('Access token ou email não encontrado')
    
    # Verificar expiração
    expires_at_str = credentials.get('expires_at')
    if expires_at_str:
        expires_at = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
        if expires_at < datetime.utcnow():
            from app.routes.microsoft_oauth_routes import _refresh_microsoft_token
            if not _refresh_microsoft_token(connection):
                raise ValueError('Não foi possível renovar token Microsoft')
            credentials = connection.get_decrypted_credentials()
            access_token = credentials.get('access_token')
    
    # Processar templates
    source_data = data.get('source_data', {})
    to_emails = config.get('to', [])
    subject_template = config.get('subject_template', '')
    body_template = config.get('body_template', '')
    body_type = config.get('body_type', 'html')
    
    to_processed = [TagProcessor.replace_tags(email, source_data) for email in to_emails]
    subject = TagProcessor.replace_tags(subject_template, source_data)
    body = TagProcessor.replace_tags(body_template, source_data)
    
    # Processar anexos
    attachments = _get_attachments(
        data, config, workflow.organization_id
    )
    
    # Enviar
    EmailService.send_via_graph_api(
        access_token=access_token,
        from_email=from_email,
        to=to_processed,
        subject=subject,
        body=body,
        body_type=body_type,
        cc=config.get('cc', []),
        bcc=config.get('bcc', []),
        attachments=attachments if attachments else None
    )
    
    activity.logger.info(f"Email Outlook enviado para {to_processed}")
    
    return {
        'success': True,
        'recipients': to_processed,
        'subject': subject
    }


def _get_attachments(data: Dict, config: Dict, organization_id) -> List[Dict]:
    """Busca anexos (PDFs) dos documentos gerados"""
    from app.models import GeneratedDocument
    
    attachments = []
    
    if not config.get('attach_documents', False):
        return attachments
    
    document_node_ids = config.get('document_node_ids', [])
    generated_documents = data.get('generated_documents', [])
    
    for doc_info in generated_documents:
        # Se document_node_ids está vazio, anexar todos
        # Se está preenchido, filtrar
        if document_node_ids and str(doc_info.get('node_id')) not in document_node_ids:
            continue
        
        document_id = doc_info.get('document_id')
        if not document_id:
            continue
        
        doc = GeneratedDocument.query.get(document_id)
        if not doc:
            continue
        
        try:
            pdf_bytes = None
            filename = f"{doc.name or 'documento'}.pdf"
            
            # Tentar baixar PDF
            if doc.pdf_file_id:
                from app.routes.google_drive_routes import get_google_credentials
                from app.services.document_generation.google_docs import GoogleDocsService
                
                google_creds = get_google_credentials(organization_id)
                if google_creds:
                    docs_service = GoogleDocsService(google_creds)
                    try:
                        pdf_bytes = docs_service.export_as_pdf(doc.google_doc_id)
                    except:
                        pass
            
            if pdf_bytes:
                attachments.append({
                    'filename': filename,
                    'content': pdf_bytes,
                    'content_type': 'application/pdf'
                })
                activity.logger.info(f'PDF anexado: {filename}')
        except Exception as e:
            activity.logger.warning(f'Erro ao anexar documento {document_id}: {e}')
    
    return attachments

