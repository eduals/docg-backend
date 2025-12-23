"""
Open Editor Controller.
"""

from flask import jsonify, g
from app.models import Template
from app.services.storage import DigitalOceanSpacesService


def open_editor(template_id: str):
    """
    Retorna URL para abrir o template no editor apropriado.

    Response:
    {
        "success": true,
        "editor_url": "https://...",
        "editor_type": "google|microsoft|uploaded"
    }
    """
    template = Template.query.filter_by(
        id=template_id,
        organization_id=g.organization_id
    ).first_or_404()

    editor_url = None
    editor_type = None

    # Determinar tipo de template e URL apropriada
    if template.storage_type == 'google' or template.google_file_id:
        # Template do Google Docs
        if template.google_file_type == 'document':
            editor_url = f"https://docs.google.com/document/d/{template.google_file_id}/edit"
        elif template.google_file_type == 'presentation':
            editor_url = f"https://docs.google.com/presentation/d/{template.google_file_id}/edit"
        else:
            editor_url = (
                template.google_file_url or
                f"https://docs.google.com/document/d/{template.google_file_id}/edit"
            )
        editor_type = 'google'

    elif template.storage_type == 'microsoft' or template.microsoft_file_id:
        # Template do Microsoft Word/PowerPoint
        editor_url = (
            f"https://office.com/m/{template.microsoft_file_type}/"
            f"viewer/action/view?resid={template.microsoft_file_id}"
        )
        editor_type = 'microsoft'

    elif template.storage_type == 'uploaded' or template.storage_file_key:
        # Template enviado - gerar URL assinada temporária
        storage_service = DigitalOceanSpacesService()
        editor_url = storage_service.generate_signed_url(
            template.storage_file_key,
            expiration=3600  # 1 hora
        )
        editor_type = 'uploaded'

    else:
        return jsonify({
            'error': 'Template não possui URL de editor disponível'
        }), 400

    return jsonify({
        'success': True,
        'editor_url': editor_url,
        'editor_type': editor_type
    })
