"""
Security Sessions Controllers.
"""

from flask import request, jsonify, g
from app.database import db
from app.models import User, UserSession
import hashlib


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


def list_sessions():
    """Lista sessões ativas do usuário"""
    user = _get_current_user()
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404

    current_token = request.headers.get('Authorization', '').replace('Bearer ', '')
    current_token_hash = hashlib.sha256(current_token.encode()).hexdigest() if current_token else None

    sessions = UserSession.query.filter_by(user_id=user.id).all()
    sessions_data = []
    for session in sessions:
        session_dict = session.to_dict()
        session_dict['is_current'] = (
            current_token_hash and
            session.session_token == current_token_hash
        )
        sessions_data.append(session_dict)

    return jsonify({
        'sessions': sessions_data
    })


def revoke_session(session_id: str):
    """Revoga uma sessão específica"""
    user = _get_current_user()
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404

    session = UserSession.query.filter_by(
        id=session_id,
        user_id=user.id
    ).first_or_404()

    db.session.delete(session)
    db.session.commit()

    return jsonify({'success': True})


def revoke_all_other_sessions():
    """Revoga todas as outras sessões (exceto a atual)"""
    user = _get_current_user()
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404

    current_token = request.headers.get('Authorization', '').replace('Bearer ', '')
    current_token_hash = hashlib.sha256(current_token.encode()).hexdigest() if current_token else None

    if current_token_hash:
        sessions = UserSession.query.filter(
            UserSession.user_id == user.id,
            UserSession.session_token != current_token_hash
        ).all()
    else:
        sessions = UserSession.query.filter_by(user_id=user.id).all()

    for session in sessions:
        db.session.delete(session)

    db.session.commit()

    return jsonify({
        'success': True,
        'revoked_count': len(sessions)
    })
