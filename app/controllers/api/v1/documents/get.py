"""
Get Document Controller.
"""

from flask import jsonify, g
from app.models import GeneratedDocument
from .helpers import doc_to_dict
import uuid


def get_document(document_id: str):
    """Retorna detalhes de um documento"""
    org_id = uuid.UUID(g.organization_id) if isinstance(g.organization_id, str) else g.organization_id
    doc = GeneratedDocument.query.filter_by(
        id=document_id,
        organization_id=org_id
    ).first_or_404()

    return jsonify(doc_to_dict(doc, include_details=True))
