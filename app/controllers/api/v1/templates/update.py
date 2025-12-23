"""
Update Template Controller.
"""

from flask import request, jsonify, g
from app.database import db
from app.models import Template
from .helpers import template_to_dict


def update_template(template_id: str):
    """Atualiza um template (nome e descrição)"""
    template = Template.query.filter_by(
        id=template_id,
        organization_id=g.organization_id
    ).first_or_404()

    data = request.get_json()

    if 'name' in data:
        if not data['name'] or not data['name'].strip():
            return jsonify({'error': 'name não pode ser vazio'}), 400
        template.name = data['name'].strip()

    if 'description' in data:
        template.description = data['description'] if data['description'] else None

    db.session.commit()

    return jsonify({
        'success': True,
        'template': template_to_dict(template, include_tags=False)
    })
