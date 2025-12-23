"""
Sync Template Controller.
"""

from flask import jsonify, g
from app.database import db
from app.models import Template
from app.services.document_generation.google_docs import GoogleDocsService
from app.routes.google_drive_routes import get_google_credentials
import logging

logger = logging.getLogger(__name__)


def sync_template(template_id: str):
    """
    Sincroniza template do Google Drive ou Microsoft OneDrive.
    Re-analisa o template e atualiza as tags detectadas.
    """
    template = Template.query.filter_by(
        id=template_id,
        organization_id=g.organization_id
    ).first_or_404()

    try:
        organization_id = g.organization_id

        # Verificar se é template do Google Drive
        if not template.google_file_id:
            return jsonify({
                'error': 'Sincronização de templates Microsoft ainda não implementada'
            }), 400

        google_creds = get_google_credentials(organization_id)
        if not google_creds:
            return jsonify({'error': 'Credenciais do Google não configuradas'}), 400

        docs_service = GoogleDocsService(google_creds)

        # Extrair tags do documento
        detected_tags = docs_service.extract_tags_from_document(template.google_file_id)

        template.detected_tags = detected_tags
        template.version += 1
        template.last_synced_at = db.func.now()
        db.session.commit()

        return jsonify({
            'success': True,
            'detected_tags': detected_tags,
            'version': template.version
        })

    except Exception as e:
        logger.error(f"Erro ao sincronizar template: {str(e)}")
        return jsonify({'error': str(e)}), 500
