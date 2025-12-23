"""
Security Two-Factor Authentication Controllers.
"""

from flask import request, jsonify, g
from app.database import db
from app.models import User, UserTwoFactorAuth
import pyotp
import qrcode
import io
import base64
import secrets
import logging

logger = logging.getLogger(__name__)


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


def get_2fa_status():
    """Retorna status do 2FA do usuário"""
    user = _get_current_user()
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404

    two_fa = UserTwoFactorAuth.query.filter_by(user_id=user.id).first()

    if not two_fa:
        return jsonify({
            'enabled': False,
            'backup_codes_count': 0
        })

    return jsonify({
        'enabled': two_fa.enabled,
        'backup_codes_count': len(two_fa.backup_codes) if two_fa.backup_codes else 0
    })


def enable_2fa():
    """Habilita 2FA - gera secret e retorna QR code"""
    user = _get_current_user()
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404

    secret = pyotp.random_base32()

    two_fa = UserTwoFactorAuth.query.filter_by(user_id=user.id).first()
    if not two_fa:
        two_fa = UserTwoFactorAuth(
            user_id=user.id,
            enabled=False,
            secret=secret
        )
        db.session.add(two_fa)
    else:
        two_fa.secret = secret
        two_fa.enabled = False

    db.session.commit()

    totp_uri = pyotp.totp.TOTP(secret).provisioning_uri(
        name=user.email,
        issuer_name='DocGen'
    )

    qr_code_base64 = None
    try:
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(totp_uri)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)

        qr_code_base64 = base64.b64encode(buffer.read()).decode()
    except ModuleNotFoundError as e:
        logger.error("PIL (Pillow) não instalada: %s", e)

    return jsonify({
        'secret': secret,
        'qr_code': f'data:image/png;base64,{qr_code_base64}' if qr_code_base64 else None,
        'uri': totp_uri
    })


def verify_2fa():
    """Verifica código 2FA e habilita"""
    user = _get_current_user()
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404

    data = request.get_json()
    code = data.get('code')

    if not code:
        return jsonify({'error': 'Código é obrigatório'}), 400

    two_fa = UserTwoFactorAuth.query.filter_by(user_id=user.id).first()
    if not two_fa or not two_fa.secret:
        return jsonify({'error': '2FA não foi inicializado. Chame /2fa/enable primeiro'}), 400

    totp = pyotp.TOTP(two_fa.secret)
    if not totp.verify(code, valid_window=1):
        return jsonify({'error': 'Código inválido'}), 400

    two_fa.enabled = True
    backup_codes = [secrets.token_hex(4) for _ in range(8)]
    two_fa.backup_codes = backup_codes

    db.session.commit()

    return jsonify({
        'success': True,
        'backup_codes': backup_codes
    })


def disable_2fa():
    """Desabilita 2FA"""
    user = _get_current_user()
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404

    data = request.get_json()
    code = data.get('code')

    two_fa = UserTwoFactorAuth.query.filter_by(user_id=user.id).first()
    if not two_fa or not two_fa.enabled:
        return jsonify({'error': '2FA não está habilitado'}), 400

    if code:
        totp = pyotp.TOTP(two_fa.secret)
        is_valid_code = totp.verify(code, valid_window=1)
        is_valid_backup = two_fa.backup_codes and code in two_fa.backup_codes

        if not (is_valid_code or is_valid_backup):
            return jsonify({'error': 'Código inválido'}), 400

        if is_valid_backup:
            two_fa.backup_codes.remove(code)

    two_fa.enabled = False
    two_fa.secret = None
    two_fa.backup_codes = None

    db.session.commit()

    return jsonify({'success': True})
