"""
OAuth Callbacks API - OAuth2 callback handlers for pieces

Endpoints:
- GET /api/v1/oauth/callback/:piece_name - OAuth callback handler
- GET /api/v1/oauth/authorize/:piece_name - Initiate OAuth flow
"""

from flask import Blueprint, request, jsonify, redirect
from uuid import UUID, uuid4
from datetime import datetime
import logging
import httpx

from app.database import db
from app.models.app_connection import AppConnection, ConnectionKey, AppConnectionType
from app.utils.credentials_encryption import encrypt_credentials
from app.pieces.base import registry

logger = logging.getLogger(__name__)

oauth_callbacks_bp = Blueprint('oauth_callbacks', __name__, url_prefix='/api/v1/oauth')


@oauth_callbacks_bp.route('/authorize/<piece_name>', methods=['GET'])
def authorize(piece_name):
    """
    Initiate OAuth flow for a piece.

    Query params:
        project_id: Project ID
        connection_name: Name for the connection
        redirect_uri: Where to redirect after OAuth completes
    """
    try:
        # Get piece
        piece = registry.get(piece_name)
        if not piece or not piece.auth:
            return jsonify({'error': 'Piece not found or does not support OAuth'}), 404

        if piece.auth.type.value != 'OAUTH2':
            return jsonify({'error': 'Piece does not support OAuth2'}), 400

        # Get connection key (global OAuth app credentials)
        connection_key = ConnectionKey.query.filter_by(piece_name=piece_name).first()
        if not connection_key:
            return jsonify({'error': 'OAuth app not configured for this piece'}), 400

        # Get OAuth config
        oauth_config = piece.auth.oauth2_config

        # Build authorization URL
        project_id = request.args.get('project_id')
        connection_name = request.args.get('connection_name', f'{piece.display_name} Connection')
        redirect_uri = request.args.get('redirect_uri', request.host_url + f'api/v1/oauth/callback/{piece_name}')

        # Store state in session or database for CSRF protection
        state = str(uuid4())

        # Build auth URL
        scope = ' '.join(oauth_config.scope) if isinstance(oauth_config.scope, list) else oauth_config.scope

        auth_url = f"{oauth_config.auth_url}?client_id={connection_key.client_id}&redirect_uri={redirect_uri}&scope={scope}&state={state}&response_type=code"

        # Store pending connection info in session/cache
        # For now, we'll pass it via state parameter
        # In production, use Redis or database

        logger.info(f"Initiating OAuth for {piece_name}")

        return jsonify({
            'auth_url': auth_url,
            'state': state
        }), 200

    except Exception as e:
        logger.error(f"Error initiating OAuth: {e}")
        return jsonify({'error': str(e)}), 500


@oauth_callbacks_bp.route('/callback/<piece_name>', methods=['GET'])
async def callback(piece_name):
    """
    OAuth callback handler.

    Query params:
        code: Authorization code
        state: State for CSRF protection
    """
    try:
        # Get authorization code
        code = request.args.get('code')
        state = request.args.get('state')

        if not code:
            error = request.args.get('error')
            error_description = request.args.get('error_description', 'OAuth authorization failed')
            return jsonify({'error': error, 'description': error_description}), 400

        # Get piece
        piece = registry.get(piece_name)
        if not piece or not piece.auth:
            return jsonify({'error': 'Piece not found'}), 404

        # Get connection key
        connection_key = ConnectionKey.query.filter_by(piece_name=piece_name).first()
        if not connection_key:
            return jsonify({'error': 'OAuth app not configured'}), 400

        # Get OAuth config
        oauth_config = piece.auth.oauth2_config

        # Decrypt client_secret
        from app.utils.credentials_encryption import decrypt_credentials
        decrypted = decrypt_credentials(connection_key.client_secret)
        client_secret = decrypted.get('client_secret')

        # Exchange code for tokens
        redirect_uri = request.host_url + f'api/v1/oauth/callback/{piece_name}'

        async with httpx.AsyncClient() as client:
            response = await client.post(
                oauth_config.token_url,
                data={
                    'grant_type': 'authorization_code',
                    'code': code,
                    'redirect_uri': redirect_uri,
                    'client_id': connection_key.client_id,
                    'client_secret': client_secret,
                }
            )

            if response.status_code != 200:
                logger.error(f"Token exchange failed: {response.text}")
                return jsonify({'error': 'Failed to exchange code for tokens'}), 400

            token_data = response.json()

        # Extract tokens
        access_token = token_data.get('access_token')
        refresh_token = token_data.get('refresh_token')
        expires_in = token_data.get('expires_in')

        if not access_token:
            return jsonify({'error': 'No access token received'}), 400

        # Calculate expiration
        expires_at = int(datetime.utcnow().timestamp()) + expires_in if expires_in else None

        # Encrypt credentials
        credentials = {
            'access_token': access_token,
            'refresh_token': refresh_token,
            'expires_at': expires_at,
        }

        encrypted_credentials = encrypt_credentials(credentials)

        logger.info(f"OAuth completed for {piece_name}")

        # Return credentials (in production, redirect to frontend with success)
        return jsonify({
            'success': True,
            'message': 'OAuth completed successfully',
            'piece_name': piece_name,
            # In production, don't return credentials - redirect to frontend
            # 'credentials': encrypted_credentials,
        }), 200

    except Exception as e:
        logger.error(f"Error in OAuth callback: {e}")
        return jsonify({'error': str(e)}), 500


@oauth_callbacks_bp.route('/refresh/<connection_id>', methods=['POST'])
async def refresh_token(connection_id):
    """
    Refresh OAuth token for a connection.

    This endpoint can be called manually or automatically when a token expires.
    """
    try:
        # Get connection
        connection = db.session.get(AppConnection, UUID(connection_id))
        if not connection:
            return jsonify({'error': 'Connection not found'}), 404

        if connection.type != AppConnectionType.OAUTH2:
            return jsonify({'error': 'Connection is not OAuth2'}), 400

        # Get piece
        piece = registry.get(connection.piece_name)
        if not piece or not piece.auth:
            return jsonify({'error': 'Piece not found'}), 404

        # Get connection key
        connection_key = ConnectionKey.query.filter_by(piece_name=connection.piece_name).first()
        if not connection_key:
            return jsonify({'error': 'OAuth app not configured'}), 400

        # Decrypt current credentials
        from app.utils.credentials_encryption import decrypt_credentials
        credentials = decrypt_credentials(connection.value)
        refresh_token = credentials.get('refresh_token')

        if not refresh_token:
            return jsonify({'error': 'No refresh token available'}), 400

        # Decrypt client_secret
        decrypted_key = decrypt_credentials(connection_key.client_secret)
        client_secret = decrypted_key.get('client_secret')

        # Get OAuth config
        oauth_config = piece.auth.oauth2_config

        # Refresh token
        async with httpx.AsyncClient() as client:
            response = await client.post(
                oauth_config.token_url,
                data={
                    'grant_type': 'refresh_token',
                    'refresh_token': refresh_token,
                    'client_id': connection_key.client_id,
                    'client_secret': client_secret,
                }
            )

            if response.status_code != 200:
                logger.error(f"Token refresh failed: {response.text}")
                # Mark connection as error
                connection.status = 'ERROR'
                db.session.commit()
                return jsonify({'error': 'Failed to refresh token'}), 400

            token_data = response.json()

        # Update credentials
        new_access_token = token_data.get('access_token')
        new_refresh_token = token_data.get('refresh_token', refresh_token)  # Some APIs don't return new refresh token
        expires_in = token_data.get('expires_in')

        expires_at = int(datetime.utcnow().timestamp()) + expires_in if expires_in else None

        new_credentials = {
            'access_token': new_access_token,
            'refresh_token': new_refresh_token,
            'expires_at': expires_at,
        }

        connection.value = encrypt_credentials(new_credentials)
        connection.status = 'ACTIVE'
        connection.updated_at = datetime.utcnow()

        db.session.commit()

        logger.info(f"Refreshed token for connection: {connection_id}")

        return jsonify({
            'success': True,
            'message': 'Token refreshed successfully'
        }), 200

    except Exception as e:
        logger.error(f"Error refreshing token: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
