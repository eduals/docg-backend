"""
Get Organization Controller.
"""

from flask import jsonify, g
from app.models import Organization


def get_organization(organization_id: str):
    """Retorna detalhes de uma organização"""
    if organization_id != g.organization_id:
        return jsonify({'error': 'Acesso negado'}), 403

    org = Organization.query.filter_by(id=organization_id).first_or_404()
    return jsonify(org.to_dict())
