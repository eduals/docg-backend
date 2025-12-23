"""
Get Signature Controller.
"""

from flask import jsonify, g
from app.models import SignatureRequest, GeneratedDocument, Workflow
import uuid


def get_signature(signature_id: str):
    """
    Retorna detalhes de uma assinatura específica.
    """
    org_id = uuid.UUID(g.organization_id) if isinstance(g.organization_id, str) else g.organization_id

    signature = SignatureRequest.query.filter_by(
        id=signature_id,
        organization_id=org_id
    ).first_or_404()

    sig_dict = signature.to_dict()

    document = GeneratedDocument.query.get(signature.generated_document_id)
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

    return jsonify(sig_dict)
