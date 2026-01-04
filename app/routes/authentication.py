"""
Authentication API - ActivePieces compatible endpoints
Handles sign-in, sign-up, OAuth, password reset, email verification
"""

from flask import Blueprint, request, jsonify, g
from werkzeug.security import generate_password_hash, check_password_hash
from app.database import db
from app.models.organization import User, Organization
from app.models.platform import Platform, Project
from app.models.permissions import ProjectMember, ProjectRole
from app.models.otp import OTP
from app.models.refresh_token import RefreshToken
from app.models.two_factor_auth import TwoFactorAuth
from app.utils.auth import generate_jwt_token
from app.utils.email import send_otp_email, send_welcome_email, send_password_reset_success_email
from app.utils.oauth import get_google_auth_url, authenticate_with_google
from app.utils.rate_limit import (
    rate_limit_auth_strict,
    rate_limit_auth_medium,
    rate_limit_signup,
    rate_limit_oauth
)
import logging
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)
auth_bp = Blueprint('authentication', __name__, url_prefix='/api/v1')


def _create_auth_response(user, platform, project):
    """
    Helper function to create authentication response with JWT and refresh tokens.

    Args:
        user: User instance
        platform: Platform instance
        project: Project instance

    Returns:
        Dictionary with user data, JWT token, and refresh token
    """
    # Generate JWT token (ActivePieces UserPrincipal structure)
    token_payload = {
        'id': str(user.id),              # User ID (not userId)
        'type': 'USER',                  # Principal type
        'platform': {                     # Platform as nested object
            'id': str(platform.id)
        },
        'projectId': str(project.id),    # Optional but useful
        'email': user.email,             # Extra field for convenience
        'platformRole': user.platform_role or 'ADMIN'
    }
    token = generate_jwt_token(token_payload)

    # Generate refresh token
    ip_address = request.remote_addr
    user_agent = request.headers.get('User-Agent', '')
    refresh_token = RefreshToken.create_refresh_token(
        user_id=user.id,
        ip_address=ip_address,
        user_agent=user_agent,
        ttl_days=30
    )

    # Build response
    response = user.to_dict(include_activepieces=True)
    response['token'] = token
    response['refreshToken'] = refresh_token.token
    response['platformId'] = str(platform.id)  # Ensure platformId is always present
    response['projectId'] = str(project.id)

    return response


@auth_bp.route('/authentication/sign-in', methods=['POST'])
@rate_limit_auth_strict()
def sign_in():
    """
    Sign in with email and password.

    Request:
        {
            "email": "user@example.com",
            "password": "password123",
            "twoFactorCode": "123456"  # Optional, required if 2FA is enabled
        }

    Response:
        {
            "id": "uuid",
            "email": "user@example.com",
            "firstName": "John",
            "lastName": "Doe",
            "verified": true,
            "platformRole": "ADMIN",
            "platformId": "uuid",
            "projectId": "uuid",
            "token": "jwt_token",
            "status": "ACTIVE",
            "trackEvents": true,
            "newsLetter": false
        }

        OR if 2FA is required but not provided:
        {
            "error": "2FA code required",
            "code": "2FA_CODE_REQUIRED",
            "requires2FA": true
        }
    """
    data = request.get_json()

    if not data or not data.get('email') or not data.get('password'):
        return jsonify({'error': 'Email and password are required'}), 400

    email = data['email'].lower().strip()
    password = data['password']
    two_factor_code = data.get('twoFactorCode')

    # Find user by email
    user = User.query.filter_by(email=email).first()

    if not user:
        return jsonify({
            'error': 'Invalid email or password',
            'code': 'INVALID_CREDENTIALS'
        }), 401

    # Check password
    if not user.password_hash or not check_password_hash(user.password_hash, password):
        return jsonify({
            'error': 'Invalid email or password',
            'code': 'INVALID_CREDENTIALS'
        }), 401

    # Check if user is active
    if user.status and user.status != 'ACTIVE':
        return jsonify({
            'error': 'User has been deactivated',
            'code': 'USER_IS_INACTIVE'
        }), 403

    # Check 2FA if enabled
    two_fa = TwoFactorAuth.query.filter_by(user_id=user.id).first()
    if two_fa and two_fa.enabled:
        if not two_factor_code:
            # 2FA is required but code not provided
            return jsonify({
                'error': '2FA code required',
                'code': '2FA_CODE_REQUIRED',
                'requires2FA': True
            }), 403

        # Verify 2FA code
        if not two_fa.verify_code(two_factor_code):
            return jsonify({
                'error': 'Invalid 2FA code',
                'code': 'INVALID_2FA_CODE'
            }), 401

    # Check email verification (optional for now)
    # if not user.verified:
    #     return jsonify({
    #         'error': 'Email is not verified',
    #         'code': 'EMAIL_IS_NOT_VERIFIED'
    #     }), 403

    # Get or create platform
    platform = None
    if user.platform_id:
        platform = Platform.query.filter_by(id=user.platform_id).first()

    if not platform:
        # Create default platform for user
        platform = Platform(
            id=uuid.uuid4(),
            name=f"{user.first_name or user.email.split('@')[0]}'s Platform"
        )
        db.session.add(platform)
        user.platform_id = platform.id
        user.platform_role = 'ADMIN'
        db.session.flush()

    # Get or create default project
    project = Project.query.filter_by(platform_id=platform.id).first()
    if not project:
        project = Project(
            id=uuid.uuid4(),
            name='my-first-project',
            display_name='My First Project',
            platform_id=platform.id
        )
        db.session.add(project)
        db.session.flush()

        # Get or create ADMIN role
        admin_role = ProjectRole.query.filter_by(
            name='ADMIN',
            type='DEFAULT',
            platform_id=None
        ).first()

        if not admin_role:
            admin_role = ProjectRole(
                id=uuid.uuid4(),
                name='ADMIN',
                type='DEFAULT',
                permissions=['*'],  # All permissions
                platform_id=None
            )
            db.session.add(admin_role)
            db.session.flush()

        # Create project membership
        membership = ProjectMember(
            id=uuid.uuid4(),
            project_id=project.id,
            user_id=user.id,
            project_role_id=admin_role.id,
            platform_id=platform.id
        )
        db.session.add(membership)

    # Update last active
    user.last_active_date = datetime.utcnow()

    db.session.commit()

    # Refresh user object to ensure all relationships are loaded
    db.session.refresh(user)

    # Generate tokens and build response
    response = _create_auth_response(user, platform, project)

    # Debug log
    logger.info(f"Sign-in response for {email}: platformId={response.get('platformId')}, projectId={response.get('projectId')}")

    return jsonify(response), 200


@auth_bp.route('/authentication/sign-up', methods=['POST'])
@rate_limit_signup()
def sign_up():
    """
    Create new account.

    Request:
        {
            "email": "user@example.com",
            "password": "password123",
            "firstName": "John",
            "lastName": "Doe",
            "trackEvents": true,
            "newsLetter": false
        }

    Response: Same as sign-in
    """
    data = request.get_json()

    # Validate required fields
    required = ['email', 'password', 'firstName', 'lastName']
    for field in required:
        if not data.get(field):
            return jsonify({'error': f'{field} is required'}), 400

    email = data['email'].lower().strip()

    # Check if user already exists
    existing = User.query.filter_by(email=email).first()
    if existing:
        return jsonify({
            'error': 'Email already registered',
            'code': 'EMAIL_ALREADY_EXISTS'
        }), 400

    # Create user
    user = User(
        id=uuid.uuid4(),
        email=email,
        first_name=data['firstName'],
        last_name=data['lastName'],
        password_hash=generate_password_hash(data['password']),
        verified=False,  # Email verification required
        track_events=data.get('trackEvents', True),
        news_letter=data.get('newsLetter', False),
        platform_role='ADMIN',
        status='ACTIVE'
    )

    # Create platform for user
    platform = Platform(
        id=uuid.uuid4(),
        name=f"{data['firstName']}'s Platform"
    )
    user.platform_id = platform.id

    # Create default organization (legacy)
    organization = Organization(
        id=uuid.uuid4(),
        name=f"{data['firstName']}'s Organization",
        slug=f"{email.split('@')[0]}-{str(uuid.uuid4())[:8]}",
        plan='free'
    )
    user.organization_id = organization.id

    db.session.add(organization)
    db.session.add(platform)
    db.session.add(user)
    db.session.flush()

    # Create default project
    project = Project(
        id=uuid.uuid4(),
        name='my-first-project',
        display_name='My First Project',
        platform_id=platform.id
    )
    db.session.add(project)
    db.session.flush()

    # Get or create ADMIN role
    admin_role = ProjectRole.query.filter_by(
        name='ADMIN',
        type='DEFAULT',
        platform_id=None
    ).first()

    if not admin_role:
        admin_role = ProjectRole(
            id=uuid.uuid4(),
            name='ADMIN',
            type='DEFAULT',
            permissions=['*'],  # All permissions
            platform_id=None
        )
        db.session.add(admin_role)
        db.session.flush()

    # Create project membership
    membership = ProjectMember(
        id=uuid.uuid4(),
        project_id=project.id,
        user_id=user.id,
        project_role_id=admin_role.id,
        platform_id=platform.id
    )
    db.session.add(membership)

    db.session.commit()

    # Refresh user object to ensure all relationships are loaded
    db.session.refresh(user)

    # Send welcome email
    try:
        send_welcome_email(email, data['firstName'])
    except Exception as e:
        logger.error(f"Failed to send welcome email to {email}: {e}")

    # Generate tokens and build response
    response = _create_auth_response(user, platform, project)

    # Debug log
    logger.info(f"Sign-up response for {email}: platformId={response.get('platformId')}, projectId={response.get('projectId')}")

    return jsonify(response), 201


@auth_bp.route('/authentication/switch-platform', methods=['POST'])
def switch_platform():
    """
    Switch to a different platform (multi-tenant switching).

    Request:
        {
            "platformId": "uuid"
        }

    Response: Same as sign-in with new token
    """
    # TODO: Implement platform switching
    # For now, return not implemented
    return jsonify({'error': 'Not implemented yet'}), 501


@auth_bp.route('/otp', methods=['POST'])
@rate_limit_auth_medium()
def send_otp():
    """
    Send OTP code for email verification or password reset.

    Request:
        {
            "email": "user@example.com",
            "type": "EMAIL_VERIFICATION" | "PASSWORD_RESET"
        }

    Response: 204 No Content
    """
    data = request.get_json()

    if not data or not data.get('email') or not data.get('type'):
        return jsonify({'error': 'Email and type are required'}), 400

    email = data['email'].lower().strip()
    otp_type = data['type']

    # Validate type
    if otp_type not in ['EMAIL_VERIFICATION', 'PASSWORD_RESET']:
        return jsonify({'error': 'Invalid OTP type'}), 400

    # For PASSWORD_RESET, verify user exists
    if otp_type == 'PASSWORD_RESET':
        user = User.query.filter_by(email=email).first()
        if not user:
            # Don't reveal if user exists or not
            return '', 204

    # Create OTP
    otp = OTP.create_otp(email, otp_type, ttl_minutes=10)

    # Send email with OTP code
    try:
        send_otp_email(email, otp.code, otp_type, expires_in=10)
        logger.info(f"OTP email sent to {email} ({otp_type})")
    except Exception as e:
        logger.error(f"Failed to send OTP email to {email}: {e}")
        # Still return 204 to not reveal if email sending failed

    # Also log for development
    logger.info(f"OTP for {email} ({otp_type}): {otp.code}")

    return '', 204


@auth_bp.route('/authn/local/reset-password', methods=['POST'])
@rate_limit_auth_strict()
def reset_password():
    """
    Reset password using OTP code.

    Request:
        {
            "email": "user@example.com",
            "otp": "123456",
            "newPassword": "newpassword123"
        }

    Response: 204 No Content
    """
    data = request.get_json()

    if not data or not data.get('email') or not data.get('otp') or not data.get('newPassword'):
        return jsonify({'error': 'Email, otp, and newPassword are required'}), 400

    email = data['email'].lower().strip()
    otp_code = data['otp']
    new_password = data['newPassword']

    # Find user
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({
            'error': 'Invalid email or OTP',
            'code': 'INVALID_OTP'
        }), 400

    # Verify OTP
    otp = OTP.query.filter_by(
        email=email,
        code=otp_code,
        type='PASSWORD_RESET',
        used=False
    ).order_by(OTP.created_at.desc()).first()

    if not otp or not otp.is_valid():
        return jsonify({
            'error': 'Invalid or expired OTP',
            'code': 'INVALID_OTP'
        }), 400

    # Update password
    user.password_hash = generate_password_hash(new_password)
    otp.mark_as_used()

    db.session.commit()

    # Send confirmation email
    try:
        send_password_reset_success_email(email)
    except Exception as e:
        logger.error(f"Failed to send password reset confirmation to {email}: {e}")

    logger.info(f"Password reset for user: {email}")

    return '', 204


@auth_bp.route('/authn/local/verify-email', methods=['POST'])
@rate_limit_auth_strict()
def verify_email():
    """
    Verify email using OTP code.

    Request:
        {
            "email": "user@example.com",
            "otp": "123456"
        }

    Response: 204 No Content
    """
    data = request.get_json()

    if not data or not data.get('email') or not data.get('otp'):
        return jsonify({'error': 'Email and otp are required'}), 400

    email = data['email'].lower().strip()
    otp_code = data['otp']

    # Find user
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({
            'error': 'Invalid email or OTP',
            'code': 'INVALID_OTP'
        }), 400

    # Verify OTP
    otp = OTP.query.filter_by(
        email=email,
        code=otp_code,
        type='EMAIL_VERIFICATION',
        used=False
    ).order_by(OTP.created_at.desc()).first()

    if not otp or not otp.is_valid():
        return jsonify({
            'error': 'Invalid or expired OTP',
            'code': 'INVALID_OTP'
        }), 400

    # Mark email as verified
    user.verified = True
    otp.mark_as_used()

    db.session.commit()

    logger.info(f"Email verified for user: {email}")

    return '', 204


@auth_bp.route('/authn/federated/login', methods=['GET'])
@rate_limit_oauth()
def federated_login():
    """
    Get OAuth login URL for federated authentication.

    Query Params:
        providerName: GOOGLE | GITHUB | SAML

    Response:
        {
            "loginUrl": "https://accounts.google.com/o/oauth2/v2/auth?..."
        }
    """
    provider_name = request.args.get('providerName')

    if not provider_name:
        return jsonify({'error': 'providerName is required'}), 400

    provider_name = provider_name.upper()

    if provider_name == 'GOOGLE':
        # Generate state for CSRF protection (optional)
        state = str(uuid.uuid4())
        login_url = get_google_auth_url(state=state)

        logger.info(f"Generated Google OAuth login URL")
        return jsonify({'loginUrl': login_url}), 200

    elif provider_name == 'GITHUB':
        return jsonify({
            'error': 'GitHub OAuth not yet implemented',
            'code': 'NOT_IMPLEMENTED'
        }), 501

    elif provider_name == 'SAML':
        return jsonify({
            'error': 'SAML not yet implemented',
            'code': 'NOT_IMPLEMENTED'
        }), 501

    else:
        return jsonify({
            'error': f'Unknown provider: {provider_name}',
            'code': 'INVALID_PROVIDER'
        }), 400


@auth_bp.route('/authn/federated/claim', methods=['POST'])
@rate_limit_oauth()
def federated_claim():
    """
    Exchange OAuth code for authentication token.

    Request:
        {
            "providerName": "GOOGLE" | "GITHUB" | "SAML",
            "code": "oauth_authorization_code"
        }

    Response: Same structure as sign-in
    """
    data = request.get_json()

    if not data or not data.get('providerName') or not data.get('code'):
        return jsonify({'error': 'providerName and code are required'}), 400

    provider_name = data['providerName'].upper()
    code = data['code']

    if provider_name == 'GOOGLE':
        # Authenticate with Google
        user_info, error = authenticate_with_google(code)

        if error:
            logger.error(f"Google OAuth failed: {error}")
            return jsonify({
                'error': error,
                'code': 'OAUTH_FAILED'
            }), 401

        email = user_info['email'].lower().strip()

        # Check if user exists
        user = User.query.filter_by(email=email).first()

        if user:
            # Existing user - sign in
            # Check if user is active
            if user.status and user.status != 'ACTIVE':
                return jsonify({
                    'error': 'User has been deactivated',
                    'code': 'USER_IS_INACTIVE'
                }), 403

            # Update user info from Google if needed
            if not user.verified:
                user.verified = True
            if not user.first_name and user_info.get('given_name'):
                user.first_name = user_info['given_name']
            if not user.last_name and user_info.get('family_name'):
                user.last_name = user_info['family_name']
            if not user.external_id:
                user.external_id = user_info['id']

            # Update last active
            user.last_active_date = datetime.utcnow()
            db.session.commit()

        else:
            # New user - sign up via OAuth
            user = User(
                id=uuid.uuid4(),
                email=email,
                first_name=user_info.get('given_name', ''),
                last_name=user_info.get('family_name', ''),
                verified=True,  # Email verified by Google
                external_id=user_info['id'],
                platform_role='ADMIN',
                status='ACTIVE',
                track_events=True,
                news_letter=False
            )

            # Create platform for user
            platform = Platform(
                id=uuid.uuid4(),
                name=f"{user_info.get('given_name', 'User')}'s Platform"
            )
            user.platform_id = platform.id

            # Create default organization (legacy)
            organization = Organization(
                id=uuid.uuid4(),
                name=f"{user_info.get('given_name', 'User')}'s Organization",
                slug=f"{email.split('@')[0]}-{str(uuid.uuid4())[:8]}",
                plan='free'
            )
            user.organization_id = organization.id

            db.session.add(organization)
            db.session.add(platform)
            db.session.add(user)
            db.session.flush()

            # Create default project
            project = Project(
                id=uuid.uuid4(),
                name='my-first-project',
                display_name='My First Project',
                platform_id=platform.id
            )
            db.session.add(project)
            db.session.flush()

            # Get or create ADMIN role
            admin_role = ProjectRole.query.filter_by(
                name='ADMIN',
                type='DEFAULT',
                platform_id=None
            ).first()

            if not admin_role:
                admin_role = ProjectRole(
                    id=uuid.uuid4(),
                    name='ADMIN',
                    type='DEFAULT',
                    permissions=['*'],
                    platform_id=None
                )
                db.session.add(admin_role)
                db.session.flush()

            # Create project membership
            membership = ProjectMember(
                id=uuid.uuid4(),
                project_id=project.id,
                user_id=user.id,
                project_role_id=admin_role.id,
                platform_id=platform.id
            )
            db.session.add(membership)

            db.session.commit()

            # Send welcome email
            try:
                send_welcome_email(email, user_info.get('given_name', 'User'))
            except Exception as e:
                logger.error(f"Failed to send welcome email to {email}: {e}")

            logger.info(f"New user registered via Google OAuth: {email}")

        # Get platform and project
        platform = Platform.query.filter_by(id=user.platform_id).first()
        project = Project.query.filter_by(platform_id=platform.id).first()

        # Generate tokens and build response
        response = _create_auth_response(user, platform, project)

        return jsonify(response), 200

    elif provider_name == 'GITHUB':
        return jsonify({
            'error': 'GitHub OAuth not yet implemented',
            'code': 'NOT_IMPLEMENTED'
        }), 501

    elif provider_name == 'SAML':
        return jsonify({
            'error': 'SAML not yet implemented',
            'code': 'NOT_IMPLEMENTED'
        }), 501

    else:
        return jsonify({
            'error': f'Unknown provider: {provider_name}',
            'code': 'INVALID_PROVIDER'
        }), 400


@auth_bp.route('/authentication/refresh', methods=['POST'])
@rate_limit_auth_strict()
def refresh_token():
    """
    Refresh JWT access token using refresh token.

    Request:
        {
            "refreshToken": "long_refresh_token_string"
        }

    Response:
        {
            "token": "new_jwt_token",
            "refreshToken": "new_refresh_token"
        }
    """
    data = request.get_json()

    if not data or not data.get('refreshToken'):
        return jsonify({'error': 'refreshToken is required'}), 400

    refresh_token_str = data['refreshToken']

    # Find refresh token
    refresh_token_obj = RefreshToken.query.filter_by(token=refresh_token_str).first()

    if not refresh_token_obj:
        return jsonify({
            'error': 'Invalid refresh token',
            'code': 'INVALID_REFRESH_TOKEN'
        }), 401

    # Validate refresh token
    if not refresh_token_obj.is_valid():
        reason = 'revoked' if refresh_token_obj.revoked else 'expired'
        return jsonify({
            'error': f'Refresh token is {reason}',
            'code': 'INVALID_REFRESH_TOKEN'
        }), 401

    # Mark token as used
    refresh_token_obj.mark_used()

    # Get user
    user = User.query.filter_by(id=refresh_token_obj.user_id).first()

    if not user:
        return jsonify({
            'error': 'User not found',
            'code': 'USER_NOT_FOUND'
        }), 404

    # Check if user is active
    if user.status and user.status != 'ACTIVE':
        return jsonify({
            'error': 'User has been deactivated',
            'code': 'USER_IS_INACTIVE'
        }), 403

    # Get platform and project
    platform = Platform.query.filter_by(id=user.platform_id).first()
    if not platform:
        return jsonify({
            'error': 'Platform not found',
            'code': 'PLATFORM_NOT_FOUND'
        }), 404

    project = Project.query.filter_by(platform_id=platform.id).first()
    if not project:
        return jsonify({
            'error': 'Project not found',
            'code': 'PROJECT_NOT_FOUND'
        }), 404

    # Revoke old refresh token
    refresh_token_obj.revoke(reason='Token refreshed')

    # Generate new tokens
    response = _create_auth_response(user, platform, project)

    logger.info(f"Token refreshed for user: {user.email}")

    return jsonify({
        'token': response['token'],
        'refreshToken': response['refreshToken']
    }), 200


@auth_bp.route('/authentication/revoke', methods=['POST'])
@rate_limit_auth_strict()
def revoke_token():
    """
    Revoke refresh token (logout).

    Request:
        {
            "refreshToken": "refresh_token_string"
        }

    Response: 204 No Content
    """
    data = request.get_json()

    if not data or not data.get('refreshToken'):
        return jsonify({'error': 'refreshToken is required'}), 400

    refresh_token_str = data['refreshToken']

    # Find refresh token
    refresh_token_obj = RefreshToken.query.filter_by(token=refresh_token_str).first()

    if refresh_token_obj:
        refresh_token_obj.revoke(reason='User logout')
        logger.info(f"Refresh token revoked for user: {refresh_token_obj.user_id}")

    return '', 204


@auth_bp.route('/authentication/revoke-all', methods=['POST'])
@rate_limit_auth_strict()
def revoke_all_tokens():
    """
    Revoke all refresh tokens for a user (logout all sessions).

    Requires authentication.

    Response: 204 No Content
    """
    # This endpoint should use JWT auth to identify user
    # For now, require userId in request body
    data = request.get_json()

    if not data or not data.get('userId'):
        return jsonify({'error': 'userId is required'}), 400

    user_id = data['userId']

    # Revoke all tokens for user
    RefreshToken.revoke_all_for_user(user_id, reason='Revoke all sessions')

    logger.info(f"All refresh tokens revoked for user: {user_id}")

    return '', 204
