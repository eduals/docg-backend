"""
Regenerate Document Controller.
"""

from flask import request, jsonify, g
from app.models import GeneratedDocument
from app.services.document_generation import DocumentGenerator
from app.services.workflow_executor import WorkflowExecutor
from app.routes.google_drive_routes import get_google_credentials
from .helpers import doc_to_dict
import logging
import uuid

logger = logging.getLogger(__name__)

def regenerate_document(document_id: str):
    """Regenera um documento existente"""
    org_id = uuid.UUID(g.organization_id) if isinstance(g.organization_id, str) else g.organization_id
    doc = GeneratedDocument.query.filter_by(
        id=document_id,
        organization_id=org_id
    ).first_or_404()

    try:
        nodes = WorkflowNode.query.filter_by(workflow_id=doc.workflow_id).count()

        if nodes > 0:
            executor = WorkflowExecutor()
            execution = executor.execute_workflow(
                workflow=doc.workflow,
                source_object_id=doc.source_object_id,
                source_object_type=doc.source_object_type,
                user_id=request.get_json().get('user_id') if request.is_json else None
            )

            if execution.generated_document_id:
                new_doc = GeneratedDocument.query.get(execution.generated_document_id)
                return jsonify({
                    'success': True,
                    'document': doc_to_dict(new_doc)
                }), 201
            else:
                return jsonify({
                    'error': 'Documento não foi gerado durante a execução'
                }), 500
        else:
            organization_id = g.organization_id
            org_id_uuid = uuid.UUID(organization_id) if isinstance(organization_id, str) else organization_id

            google_creds = get_google_credentials(organization_id)
            if not google_creds:
                return jsonify({'error': 'Credenciais do Google não configuradas'}), 400

            generator = DocumentGenerator(google_creds)

            new_doc = generator.generate_from_workflow(
                workflow=doc.workflow,
                source_data=doc.generated_data,
                source_object_id=doc.source_object_id,
                user_id=request.get_json().get('user_id') if request.is_json else None,
                organization_id=org_id_uuid
            )

            return jsonify({
                'success': True,
                'document': doc_to_dict(new_doc)
            }), 201

    except Exception as e:
        logger.error(f"Erro ao regenerar documento: {str(e)}")
        return jsonify({'error': str(e)}), 500
