"""
Two-Factor Authentication Endpoints
Setup, verify, and manage 2FA
"""
from flask import Blueprint, request, jsonify, g
from app.database import db
from app.models.organization import User
from app.models.two_factor_auth import TwoFactorAuth
from app.utils.auth import require_jwt_auth
from app.utils.rate_limit import rate_limit_auth_strict
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
two_factor_bp = Blueprint('two_factor', __name__, url_prefix='/api/v1/authn/2fa')


@two_factor_bp.route('/setup', methods=['POST'])
@require_jwt_auth
@rate_limit_auth_strict()
def setup_2fa():
    """
    Setup 2FA for the current user.
    Generates QR code and backup codes.

    Response:
        {
            "qrCode": "data:image/png;base64,...",
            "secret": "BASE32SECRET",
            "backupCodes": ["CODE1", "CODE2", ...]
        }
    """
    user_id = g.user_id
    user = User.query.filter_by(id=user_id).first()

    if not user:
        return jsonify({'error': 'User not found'}), 404

    # Check if already exists
    two_fa = TwoFactorAuth.query.filter_by(user_id=user_id).first()

    if two_fa and two_fa.enabled:
        return jsonify({
            'error': '2FA is already enabled. Disable it first to set up again.',
            'code': '2FA_ALREADY_ENABLED'
        }), 400

    if not two_fa:
        # Create new 2FA setup
        two_fa = TwoFactorAuth.create_for_user(user_id)
    else:
        # Regenerate secret and backup codes
        two_fa.secret = TwoFactorAuth.generate_secret()
        two_fa.backup_codes = ','.join(TwoFactorAuth.generate_backup_codes())
        two_fa.enabled = False
        two_fa.verified = False
        db.session.commit()

    # Generate QR code
    qr_code = two_fa.get_qr_code_base64(user.email)
    backup_codes = two_fa.get_backup_codes()

    logger.info(f"2FA setup initiated for user: {user.email}")

    return jsonify({
        'qrCode': qr_code,
        'secret': two_fa.secret,
        'backupCodes': backup_codes
    }), 200


@two_factor_bp.route('/verify', methods=['POST'])
@require_jwt_auth
@rate_limit_auth_strict()
def verify_2fa():
    """
    Verify TOTP code and enable 2FA.

    Request:
        {
            "code": "123456"
        }

    Response: 204 No Content
    """
    data = request.get_json()

    if not data or not data.get('code'):
        return jsonify({'error': 'code is required'}), 400

    code = data['code']
    user_id = g.user_id

    # Get 2FA setup
    two_fa = TwoFactorAuth.query.filter_by(user_id=user_id).first()

    if not two_fa:
        return jsonify({
            'error': '2FA not set up. Call /setup first.',
            'code': '2FA_NOT_SETUP'
        }), 400

    # Verify code
    if not two_fa.verify_code(code):
        return jsonify({
            'error': 'Invalid code',
            'code': 'INVALID_2FA_CODE'
        }), 401

    # Enable 2FA
    two_fa.enable()

    logger.info(f"2FA enabled for user: {user_id}")

    return '', 204


@two_factor_bp.route('/disable', methods=['POST'])
@require_jwt_auth
@rate_limit_auth_strict()
def disable_2fa():
    """
    Disable 2FA for the current user.

    Request:
        {
            "code": "123456"  # Current TOTP code or backup code
        }

    Response: 204 No Content
    """
    data = request.get_json()

    if not data or not data.get('code'):
        return jsonify({'error': 'code is required to disable 2FA'}), 400

    code = data['code']
    user_id = g.user_id

    # Get 2FA setup
    two_fa = TwoFactorAuth.query.filter_by(user_id=user_id).first()

    if not two_fa or not two_fa.enabled:
        return jsonify({
            'error': '2FA is not enabled',
            'code': '2FA_NOT_ENABLED'
        }), 400

    # Verify code before disabling
    if not two_fa.verify_code(code):
        return jsonify({
            'error': 'Invalid code',
            'code': 'INVALID_2FA_CODE'
        }), 401

    # Disable 2FA
    two_fa.disable()

    logger.info(f"2FA disabled for user: {user_id}")

    return '', 204


@two_factor_bp.route('/status', methods=['GET'])
@require_jwt_auth
def get_2fa_status():
    """
    Get 2FA status for the current user.

    Response:
        {
            "enabled": true,
            "verified": true,
            "backupCodesRemaining": 8
        }
    """
    user_id = g.user_id

    # Get 2FA setup
    two_fa = TwoFactorAuth.query.filter_by(user_id=user_id).first()

    if not two_fa:
        return jsonify({
            'enabled': False,
            'verified': False,
            'backupCodesRemaining': 0
        }), 200

    backup_codes = two_fa.get_backup_codes()

    return jsonify({
        'enabled': two_fa.enabled,
        'verified': two_fa.verified,
        'backupCodesRemaining': len(backup_codes)
    }), 200


@two_factor_bp.route('/regenerate-backup-codes', methods=['POST'])
@require_jwt_auth
@rate_limit_auth_strict()
def regenerate_backup_codes():
    """
    Generate new backup codes.

    Request:
        {
            "code": "123456"  # Current TOTP code
        }

    Response:
        {
            "backupCodes": ["CODE1", "CODE2", ...]
        }
    """
    data = request.get_json()

    if not data or not data.get('code'):
        return jsonify({'error': 'code is required'}), 400

    code = data['code']
    user_id = g.user_id

    # Get 2FA setup
    two_fa = TwoFactorAuth.query.filter_by(user_id=user_id).first()

    if not two_fa or not two_fa.enabled:
        return jsonify({
            'error': '2FA is not enabled',
            'code': '2FA_NOT_ENABLED'
        }), 400

    # Verify code
    if not two_fa.verify_code(code):
        return jsonify({
            'error': 'Invalid code',
            'code': 'INVALID_2FA_CODE'
        }), 401

    # Regenerate backup codes
    backup_codes = two_fa.regenerate_backup_codes()

    logger.info(f"Backup codes regenerated for user: {user_id}")

    return jsonify({
        'backupCodes': backup_codes
    }), 200
