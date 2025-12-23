"""
Create Template Controller.
"""

from flask import request, jsonify, g
from app.database import db
from app.models import Template
from app.services.document_generation.google_docs import GoogleDocsService
from app.routes.google_drive_routes import get_google_credentials
from .helpers import template_to_dict
import logging

logger = logging.getLogger(__name__)


def create_template():
    """
    Registra um template do Google Drive ou Microsoft OneDrive.

    Body:
    {
        "name": "Quote Template",
        "description": "Template para cotações",
        "google_file_id": "1abc...",  // obrigatório se for Google
        "google_file_type": "document",  // document ou presentation
        "microsoft_file_id": "abc123...",  // obrigatório se for Microsoft
        "microsoft_file_type": "word"  // word ou powerpoint
    }
    """
    data = request.get_json()

    # Validar que tem pelo menos Google ou Microsoft
    has_google = data.get('google_file_id') and data.get('google_file_type')
    has_microsoft = data.get('microsoft_file_id') and data.get('microsoft_file_type')

    if not has_google and not has_microsoft:
        return jsonify({
            'error': 'É necessário fornecer google_file_id/google_file_type ou microsoft_file_id/microsoft_file_type'
        }), 400

    if not data.get('name'):
        return jsonify({'error': 'name é obrigatório'}), 400

    # Validar tipos
    if has_google:
        if data['google_file_type'] not in ['document', 'presentation']:
            return jsonify({'error': 'google_file_type deve ser document ou presentation'}), 400

    if has_microsoft:
        if data['microsoft_file_type'] not in ['word', 'powerpoint']:
            return jsonify({'error': 'microsoft_file_type deve ser word ou powerpoint'}), 400

    # Extrair tags do template (apenas para Google por enquanto)
    detected_tags = []
    if has_google:
        try:
            organization_id = g.organization_id
            if organization_id:
                google_creds = get_google_credentials(organization_id)
                if google_creds:
                    docs_service = GoogleDocsService(google_creds)
                    detected_tags = docs_service.extract_tags_from_document(data['google_file_id'])
        except Exception as e:
            logger.warning(f"Não foi possível extrair tags: {str(e)}")
            detected_tags = []

    # Criar template
    template = Template(
        organization_id=g.organization_id,
        name=data['name'],
        description=data.get('description'),
        detected_tags=detected_tags,
        created_by=data.get('user_id')
    )

    # Configurar Google se fornecido
    if has_google:
        template.google_file_id = data['google_file_id']
        template.google_file_type = data['google_file_type']
        template.google_file_url = (
            f"https://docs.google.com/document/d/{data['google_file_id']}/edit"
            if data['google_file_type'] == 'document'
            else f"https://docs.google.com/presentation/d/{data['google_file_id']}/edit"
        )
        template.storage_type = 'google'

    # Configurar Microsoft se fornecido
    if has_microsoft:
        template.microsoft_file_id = data['microsoft_file_id']
        template.microsoft_file_type = data['microsoft_file_type']
        template.storage_type = 'microsoft'

    db.session.add(template)
    db.session.commit()

    return jsonify({
        'success': True,
        'template': template_to_dict(template, include_tags=True)
    }), 201
