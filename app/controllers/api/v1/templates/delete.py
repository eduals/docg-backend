"""
Delete Template Controller.
"""

from flask import jsonify, g
from app.database import db
from app.models import Template
from app.services.storage import DigitalOceanSpacesService
import logging

logger = logging.getLogger(__name__)


def delete_template(template_id: str):
    """Deleta um template"""
    template = Template.query.filter_by(
        id=template_id,
        organization_id=g.organization_id
    ).first_or_404()

    # Verificar se tem workflows usando
    if template.workflows.count() > 0:
        return jsonify({
            'error': 'Template está sendo usado por workflows. Remova os workflows primeiro.'
        }), 400

    # Se for template enviado, deletar do DigitalOcean Spaces também
    if template.storage_type == 'uploaded' and template.storage_file_key:
        try:
            storage_service = DigitalOceanSpacesService()
            storage_service.delete_file(template.storage_file_key)
        except Exception as e:
            logger.warning(f"Erro ao deletar arquivo do Spaces: {str(e)}")
            # Continuar mesmo se falhar deletar do Spaces

    db.session.delete(template)
    db.session.commit()

    return jsonify({'success': True})
