"""
Update Organization Controller.
"""

from flask import request, jsonify, g
from app.database import db
from app.models import Organization


def update_organization(organization_id: str):
    """Atualiza uma organização"""
    if organization_id != g.organization_id:
        return jsonify({'error': 'Acesso negado'}), 403

    org = Organization.query.filter_by(id=organization_id).first_or_404()
    data = request.get_json()

    allowed_fields = ['name', 'billing_email']

    for field in allowed_fields:
        if field in data:
            setattr(org, field, data[field])

    db.session.commit()

    return jsonify({
        'success': True,
        'organization': org.to_dict()
    })
