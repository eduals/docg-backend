"""
Get Template Controller.
"""

from flask import jsonify, g
from app.models import Template
from .helpers import template_to_dict


def get_template(template_id: str):
    """Retorna detalhes de um template"""
    template = Template.query.filter_by(
        id=template_id,
        organization_id=g.organization_id
    ).first_or_404()

    return jsonify(template_to_dict(template, include_tags=True))
