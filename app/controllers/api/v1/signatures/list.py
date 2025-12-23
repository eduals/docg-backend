"""
List Signatures Controller.
"""

from flask import request, jsonify, g
from app.models import SignatureRequest, GeneratedDocument, Workflow
from datetime import datetime
import uuid


def list_signatures():
    """
    Lista assinaturas da organização com paginação e filtros.

    Query params:
    - page: número da página (default: 1)
    - per_page: itens por página (default: 20)
    - status: filtrar por status
    - provider: filtrar por provedor
    - date_from: data inicial (ISO format)
    - date_to: data final (ISO format)
    """
    org_id = uuid.UUID(g.organization_id) if isinstance(g.organization_id, str) else g.organization_id

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status')
    provider = request.args.get('provider')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')

    query = SignatureRequest.query.filter_by(organization_id=org_id)

    if status:
        query = query.filter_by(status=status)

    if provider:
        query = query.filter_by(provider=provider.lower())

    if date_from:
        try:
            date_from_obj = datetime.fromisoformat(date_from.replace('Z', '+00:00'))
            query = query.filter(SignatureRequest.created_at >= date_from_obj)
        except ValueError:
            return jsonify({
                'error': 'date_from deve estar no formato ISO (ex: 2024-01-01T00:00:00Z)'
            }), 400

    if date_to:
        try:
            date_to_obj = datetime.fromisoformat(date_to.replace('Z', '+00:00'))
            query = query.filter(SignatureRequest.created_at <= date_to_obj)
        except ValueError:
            return jsonify({
                'error': 'date_to deve estar no formato ISO (ex: 2024-01-01T00:00:00Z)'
            }), 400

    query = query.order_by(SignatureRequest.created_at.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    signatures = []
    for sig in pagination.items:
        sig_dict = sig.to_dict()

        document = GeneratedDocument.query.get(sig.generated_document_id)
        if document:
            sig_dict['document'] = {
                'id': str(document.id),
                'name': document.name,
                'google_doc_url': document.google_doc_url,
                'pdf_url': document.pdf_url,
                'status': document.status
            }

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
