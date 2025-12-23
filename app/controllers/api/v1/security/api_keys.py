"""
Security API Keys Controllers.
"""

from flask import request, jsonify, g
from app.database import db
from app.models import User, ApiKey
import hashlib
import secrets
from datetime import datetime, timedelta


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


def list_api_keys():
    """Lista API keys do usuário"""
    user = _get_current_user()
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404

    keys = ApiKey.query.filter_by(
        user_id=user.id,
        organization_id=g.organization_id
    ).all()

    return jsonify({
        'keys': [key.to_dict() for key in keys]
    })


def create_api_key():
    """Cria nova API key"""
    user = _get_current_user()
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404

    data = request.get_json(silent=True) or {}
    name = data.get('name', 'API Key')
    expires_in_days = data.get('expires_in_days')

    random_string = secrets.token_urlsafe(32)
    full_key = f'dg_{random_string}'

    key_hash = hashlib.sha256(full_key.encode()).hexdigest()

    expires_at = None
    if expires_in_days:
        expires_at = datetime.utcnow() + timedelta(days=expires_in_days)

    api_key = ApiKey(
        user_id=user.id,
        organization_id=g.organization_id,
        key_prefix='dg_',
        key_hash=key_hash,
        name=name,
        expires_at=expires_at
    )

    db.session.add(api_key)
    db.session.commit()

    return jsonify({
        'key': full_key,
        'key_id': str(api_key.id)
    }), 201


def revoke_api_key(key_id: str):
    """Revoga uma API key"""
    user = _get_current_user()
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404

    api_key = ApiKey.query.filter_by(
        id=key_id,
        user_id=user.id,
        organization_id=g.organization_id
    ).first_or_404()

    db.session.delete(api_key)
    db.session.commit()

    return jsonify({'success': True})
