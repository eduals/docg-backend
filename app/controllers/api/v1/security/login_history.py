"""
Security Login History Controller.
"""

from flask import request, jsonify, g
from app.models import User, LoginHistory


def _get_current_user():
    """Helper para obter usuário atual baseado no email"""
    user_email_header = request.headers.get('X-User-Email')
    user_email_query = request.args.get('user_email')
    user_email = user_email_header or user_email_query

    if not user_email:
        return None

    user = User.query.filter_by(
        email=user_email,
        organization_id=g.organization_id
    ).first()

    return user


def get_login_history():
    """Retorna histórico de login do usuário (com paginação)"""
    user = _get_current_user()
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404

    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', type=int) or request.args.get('per_page', 20, type=int)

    limit = min(limit, 100)

    history = LoginHistory.query.filter_by(user_id=user.id)\
        .order_by(LoginHistory.created_at.desc())\
        .paginate(page=page, per_page=limit, error_out=False)

    return jsonify({
        'history': [entry.to_dict() for entry in history.items],
        'page': page,
        'limit': limit,
        'total': history.total
    })
