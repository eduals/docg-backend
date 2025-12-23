"""
Delete Document Controller.
"""

from flask import jsonify, g
from app.database import db
from app.models import GeneratedDocument
import uuid


def delete_document(document_id: str):
    """Deleta um documento gerado"""
    org_id = uuid.UUID(g.organization_id) if isinstance(g.organization_id, str) else g.organization_id
    doc = GeneratedDocument.query.filter_by(
        id=document_id,
        organization_id=org_id
    ).first_or_404()

    db.session.delete(doc)
    db.session.commit()

    return jsonify({'success': True})
