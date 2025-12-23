"""
Delete User Controller.
"""

from flask import jsonify, g
from app.database import db
from app.models import User


def delete_user(user_id: str):
    """Deleta um usuário"""
    user = User.query.filter_by(
        id=user_id,
        organization_id=g.organization_id
    ).first_or_404()

    # Não permitir deletar último admin
    if user.is_admin():
        admin_count = User.query.filter_by(
            organization_id=g.organization_id,
            role='admin'
        ).count()

        if admin_count <= 1:
            return jsonify({
                'error': 'Não é possível deletar o último administrador'
            }), 400

    db.session.delete(user)
    db.session.commit()

    return jsonify({'success': True})
