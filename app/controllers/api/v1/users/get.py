"""
Get User Controller.
"""

from flask import request, jsonify, g
from app.models import User


def get_user(user_id: str):
    """Retorna detalhes de um usuário"""
    user = User.query.filter_by(
        id=user_id,
        organization_id=g.organization_id
    ).first_or_404()

    return jsonify(user.to_dict())


def get_current_user():
    """Retorna dados do usuário atual baseado no email"""
    user_email = request.headers.get('X-User-Email') or request.args.get('user_email')

    if not user_email:
        return jsonify({'error': 'user_email é obrigatório'}), 400

    user = User.query.filter_by(
        email=user_email,
        organization_id=g.organization_id
    ).first()

    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404

    return jsonify(user.to_dict())
