"""
Update User Controller.
"""

from flask import request, jsonify, g
from app.database import db
from app.models import User


def update_user(user_id: str):
    """Atualiza um usuário"""
    user = User.query.filter_by(
        id=user_id,
        organization_id=g.organization_id
    ).first_or_404()

    data = request.get_json()

    if 'name' in data:
        user.name = data['name']

    if 'role' in data:
        user.role = data['role']

    db.session.commit()

    return jsonify({
        'success': True,
        'user': user.to_dict()
    })
