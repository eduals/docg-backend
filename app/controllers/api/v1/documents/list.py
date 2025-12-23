"""
List Documents Controller.
"""

from flask import request, jsonify, g
from app.models import GeneratedDocument
from .helpers import doc_to_dict
import uuid


def list_documents():
    """Lista documentos gerados da organização"""
    org_id = uuid.UUID(g.organization_id) if isinstance(g.organization_id, str) else g.organization_id

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status')
    workflow_id = request.args.get('workflow_id')
    object_type = request.args.get('object_type')
    object_id = request.args.get('object_id')

    query = GeneratedDocument.query.filter_by(organization_id=org_id)

    if status:
        query = query.filter_by(status=status)
    if workflow_id:
        query = query.filter_by(workflow_id=workflow_id)
    if object_type:
        query = query.filter_by(source_object_type=object_type)
    if object_id:
        query = query.filter_by(source_object_id=object_id)

    query = query.order_by(GeneratedDocument.created_at.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'documents': [doc_to_dict(d) for d in pagination.items],
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': page
    })
