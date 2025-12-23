"""
User Preferences Controllers.
"""

from flask import request, jsonify, g
from app.database import db
from app.models import User, UserPreference, UserNotificationPreference
import logging

logger = logging.getLogger(__name__)


def _get_user_from_email():
    """Helper para obter usuário pelo email"""
    user_email_header = request.headers.get('X-User-Email')
    user_email_query = request.args.get('user_email')
    user_email = user_email_header or user_email_query

    if not user_email:
        return None, jsonify({
            'error': 'user_email é obrigatório',
            'code': 'MISSING_USER_EMAIL',
        }), 400

    user = User.query.filter_by(
        email=user_email,
        organization_id=g.organization_id
    ).first()

    if not user:
        return None, jsonify({'error': 'Usuário não encontrado'}), 404

    return user, None, None


def get_user_preferences():
    """Retorna preferências do usuário atual"""
    user, error_response, status_code = _get_user_from_email()
    if error_response:
        return error_response, status_code

    preference = UserPreference.query.filter_by(user_id=user.id).first()
    if not preference:
        preference = UserPreference(user_id=user.id)
        db.session.add(preference)
        db.session.commit()

    return jsonify(preference.to_dict())


def update_user_preferences():
    """Atualiza preferências do usuário atual"""
    user, error_response, status_code = _get_user_from_email()
    if error_response:
        return error_response, status_code

    data = request.get_json()

    preference = UserPreference.query.filter_by(user_id=user.id).first()
    if not preference:
        preference = UserPreference(user_id=user.id)
        db.session.add(preference)

    if 'language' in data:
        preference.language = data['language']
    if 'date_format' in data:
        preference.date_format = data['date_format']
    if 'time_format' in data:
        preference.time_format = data['time_format']
    if 'timezone' in data:
        preference.timezone = data['timezone']
    if 'units' in data:
        preference.units = data['units']

    db.session.commit()

    return jsonify({
        'success': True,
        'preferences': preference.to_dict()
    })


def get_user_notification_preferences():
    """Retorna preferências de notificação do usuário atual"""
    user, error_response, status_code = _get_user_from_email()
    if error_response:
        return error_response, status_code

    preference = UserNotificationPreference.query.filter_by(user_id=user.id).first()
    if not preference:
        preference = UserNotificationPreference(user_id=user.id)
        db.session.add(preference)
        db.session.commit()

    return jsonify(preference.to_dict())


def update_user_notification_preferences():
    """Atualiza preferências de notificação do usuário atual"""
    user, error_response, status_code = _get_user_from_email()
    if error_response:
        return error_response, status_code

    data = request.get_json()

    preference = UserNotificationPreference.query.filter_by(user_id=user.id).first()
    if not preference:
        preference = UserNotificationPreference(user_id=user.id)
        db.session.add(preference)

    if 'email_enabled' in data:
        preference.email_enabled = data['email_enabled']
    if 'email_document_generated' in data:
        preference.email_document_generated = data['email_document_generated']
    if 'email_document_signed' in data:
        preference.email_document_signed = data['email_document_signed']
    if 'email_workflow_executed' in data:
        preference.email_workflow_executed = data['email_workflow_executed']
    if 'email_workflow_failed' in data:
        preference.email_workflow_failed = data['email_workflow_failed']

    db.session.commit()

    return jsonify({
        'success': True,
        'preferences': preference.to_dict()
    })
