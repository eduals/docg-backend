"""
Rotas para gerenciar assinaturas (SignatureRequest).

Fornece endpoints para listar assinaturas da organização com paginação e filtros.
"""

from flask import Blueprint, request, jsonify, g
from app.database import db
from app.models import SignatureRequest, GeneratedDocument, Workflow
from app.utils.auth import require_auth, require_org
from app.utils.hubspot_auth import flexible_hubspot_auth
from datetime import datetime
import logging
import uuid

logger = logging.getLogger(__name__)
signatures_bp = Blueprint('signatures', __name__, url_prefix='/api/v1/signatures')


@signatures_bp.route('', methods=['GET'])
@flexible_hubspot_auth
@require_org
def list_signatures():
    """
    Lista assinaturas da organização com paginação e filtros.
    
    Query params:
    - page: número da página (default: 1)
    - per_page: itens por página (default: 20)
    - status: filtrar por status (pending, sent, viewed, signed, declined, expired, error)
    - provider: filtrar por provedor (clicksign, zapsign, etc)
    - date_from: data inicial (ISO format)
    - date_to: data final (ISO format)
    
    Response:
    {
        "signatures": [...],
        "total": 100,
        "pages": 5,
        "current_page": 1
    }
    """
    # Converter organization_id para UUID se for string
    org_id = uuid.UUID(g.organization_id) if isinstance(g.organization_id, str) else g.organization_id
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status')
    provider = request.args.get('provider')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    
    # Construir query base
    query = SignatureRequest.query.filter_by(organization_id=org_id)
    
    # Aplicar filtros
    if status:
        query = query.filter_by(status=status)
    
    if provider:
        query = query.filter_by(provider=provider.lower())
    
    if date_from:
        try:
            date_from_obj = datetime.fromisoformat(date_from.replace('Z', '+00:00'))
            query = query.filter(SignatureRequest.created_at >= date_from_obj)
        except ValueError:
            return jsonify({'error': 'date_from deve estar no formato ISO (ex: 2024-01-01T00:00:00Z)'}), 400
    
    if date_to:
        try:
            date_to_obj = datetime.fromisoformat(date_to.replace('Z', '+00:00'))
            query = query.filter(SignatureRequest.created_at <= date_to_obj)
        except ValueError:
            return jsonify({'error': 'date_to deve estar no formato ISO (ex: 2024-01-01T00:00:00Z)'}), 400
    
    # Ordenar por data de criação (mais recente primeiro)
    query = query.order_by(SignatureRequest.created_at.desc())
    
    # Paginar
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    # Construir resposta com dados relacionados
    signatures = []
    for sig in pagination.items:
        sig_dict = sig.to_dict()
        
        # Buscar documento relacionado
        document = GeneratedDocument.query.get(sig.generated_document_id)
        if document:
            sig_dict['document'] = {
                'id': str(document.id),
                'name': document.name,
                'google_doc_url': document.google_doc_url,
                'pdf_url': document.pdf_url,
                'status': document.status
            }
            
            # Buscar workflow relacionado se existir
            if document.workflow_id:
                workflow = Workflow.query.get(document.workflow_id)
                if workflow:
                    sig_dict['workflow'] = {
                        'id': str(workflow.id),
                        'name': workflow.name
                    }
        else:
            sig_dict['document'] = None
            sig_dict['workflow'] = None
        
        signatures.append(sig_dict)
    
    return jsonify({
        'signatures': signatures,
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': page
    })


@signatures_bp.route('/<signature_id>', methods=['GET'])
@flexible_hubspot_auth
@require_auth
@require_org
def get_signature(signature_id):
    """
    Retorna detalhes de uma assinatura específica.
    
    Response:
    {
        "id": "uuid",
        "provider": "clicksign",
        "status": "signed",
        ...
        "document": {...},
        "workflow": {...}
    }
    """
    org_id = uuid.UUID(g.organization_id) if isinstance(g.organization_id, str) else g.organization_id
    
    signature = SignatureRequest.query.filter_by(
        id=signature_id,
        organization_id=org_id
    ).first_or_404()
    
    sig_dict = signature.to_dict()
    
    # Buscar documento relacionado
    document = GeneratedDocument.query.get(signature.generated_document_id)
    if document:
        sig_dict['document'] = {
            'id': str(document.id),
            'name': document.name,
            'google_doc_url': document.google_doc_url,
            'pdf_url': document.pdf_url,
            'status': document.status
        }
        
        # Buscar workflow relacionado se existir
        if document.workflow_id:
            workflow = Workflow.query.get(document.workflow_id)
            if workflow:
                sig_dict['workflow'] = {
                    'id': str(workflow.id),
                    'name': workflow.name
                }
    else:
        sig_dict['document'] = None
        sig_dict['workflow'] = None
    
    return jsonify(sig_dict)


@signatures_bp.route('/<signature_id>/signers', methods=['GET'])
@flexible_hubspot_auth
@require_auth
@require_org
def get_signers_status(signature_id):
    """
    Retorna status detalhado de cada signatário.

    Feature 11: Melhorias em Signatures

    Response:
    {
        "signature_request_id": "uuid",
        "status": "pending|sent|signed|declined|expired",
        "provider": "clicksign|zapsign",
        "expires_at": "ISO8601",
        "all_signed": false,
        "signers": [
            {
                "email": "user@example.com",
                "status": "pending|viewed|signed|declined",
                "signed_at": "ISO8601|null"
            }
        ]
    }
    """
    org_id = uuid.UUID(g.organization_id) if isinstance(g.organization_id, str) else g.organization_id

    signature_request = SignatureRequest.query.filter_by(
        id=signature_id,
        organization_id=org_id
    ).first_or_404()

    # Construir lista de signatários
    signers = []
    if signature_request.signers_status:
        for email, status in signature_request.signers_status.items():
            signer_info = {
                'email': email,
                'status': status,
                'signed_at': None,  # TODO: Armazenar timestamp individual por signatário
            }

            # Se assinado e temos completed_at, usar como aproximação
            if status == 'signed' and signature_request.completed_at:
                signer_info['signed_at'] = signature_request.completed_at.isoformat()

            signers.append(signer_info)
    else:
        # Fallback: Se não tiver signers_status, usar signers (lista de emails)
        if hasattr(signature_request, 'signers') and signature_request.signers:
            for email in signature_request.signers:
                signers.append({
                    'email': email,
                    'status': signature_request.status,  # Status geral
                    'signed_at': signature_request.completed_at.isoformat() if signature_request.completed_at else None,
                })

    return jsonify({
        'signature_request_id': str(signature_request.id),
        'status': signature_request.status,
        'provider': signature_request.provider,
        'expires_at': signature_request.expires_at.isoformat() if signature_request.expires_at else None,
        'all_signed': signature_request.all_signed(),
        'signers': signers,
    }), 200
