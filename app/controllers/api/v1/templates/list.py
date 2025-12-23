"""
List Templates Controller.
"""

from flask import request, jsonify, g
from app.models import Template
from .helpers import template_to_dict


def list_templates():
    """Lista templates da organização (apenas registrados no banco)"""
    org_id = g.organization_id
    file_type = request.args.get('type')  # document, presentation

    query = Template.query.filter_by(organization_id=org_id)

    if file_type:
        query = query.filter_by(google_file_type=file_type)

    templates = query.order_by(Template.updated_at.desc()).all()

    return jsonify({
        'templates': [template_to_dict(t) for t in templates]
    })
