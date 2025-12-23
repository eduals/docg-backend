"""
Template Helpers - Funções auxiliares para controllers de templates.
"""

from app.models import Template


def template_to_dict(template: Template, include_tags: bool = False) -> dict:
    """Converte template para dicionário"""
    result = {
        'id': str(template.id),
        'name': template.name,
        'description': template.description,
        'google_file_id': template.google_file_id,
        'google_file_type': template.google_file_type,
        'google_file_url': template.google_file_url,
        'microsoft_file_id': template.microsoft_file_id,
        'microsoft_file_type': template.microsoft_file_type,
        'thumbnail_url': template.thumbnail_url,
        'version': template.version,
        'created_at': template.created_at.isoformat() if template.created_at else None,
        'updated_at': template.updated_at.isoformat() if template.updated_at else None,
        'storage_type': template.storage_type,
        'storage_file_url': template.storage_file_url,
        'storage_file_key': template.storage_file_key,
        'file_size': template.file_size,
        'file_mime_type': template.file_mime_type
    }

    if include_tags:
        result['detected_tags'] = template.detected_tags or []

    return result
