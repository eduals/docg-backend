from flask import Blueprint, request, jsonify, g
from app.database import db
from app.models import GoogleDriveConfig, GoogleOAuthToken, OrganizationFeature
from app.utils.hubspot_auth import flexible_hubspot_auth
from app.utils.auth import require_org
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)
settings_bp = Blueprint('settings', __name__, url_prefix='/api/v1/settings')


def get_google_credentials(organization_id):
    """Obter credenciais Google para uma organização"""
    token = GoogleOAuthToken.query.filter_by(organization_id=organization_id).first()
    
    if not token:
        return None
    
    try:
        creds_data = json.loads(token.access_token)
        creds = Credentials.from_authorized_user_info(creds_data)
        
        # Se token expirou, tentar renovar usando refresh_token
        if creds.expired or token.is_expired():
            if creds.refresh_token:
                try:
                    creds.refresh(Request())
                    # Atualizar no banco após renovação bem-sucedida
                    token.access_token = creds.to_json()
                    token.token_expiry = creds.expiry
                    db.session.commit()
                except Exception as refresh_error:
                    logger.warning(f"Error refreshing token: {refresh_error}")
                    return None
            else:
                return None
        
        return creds
    except Exception as e:
        logger.error(f"Error getting credentials: {e}")
        return None


@settings_bp.route('', methods=['GET'])
@flexible_hubspot_auth
@require_org
def get_settings():
    """Retorna configurações da organização"""
    try:
        organization_id = g.organization_id
        
        # Buscar configuração do Google Drive
        config = GoogleDriveConfig.query.filter_by(organization_id=organization_id).first()
        
        # Buscar token do Google para verificar status
        google_token = GoogleOAuthToken.query.filter_by(organization_id=organization_id).first()
        
        # Verificar status do Google Drive
        google_drive_status = 'disconnected'
        if google_token:
            creds = get_google_credentials(organization_id)
            if creds:
                google_drive_status = 'connected'
            else:
                google_drive_status = 'disconnected'
        
        # Verificar status do ClickSign
        clicksign_status = 'not_configured'
        clicksign_feature = OrganizationFeature.query.filter_by(
            organization_id=organization_id,
            feature_name='clicksign'
        ).first()
        if clicksign_feature:
            clicksign_status = 'connected' if clicksign_feature.enabled else 'disconnected'
        
        # Montar settings
        settings = {
            'templatesFolderId': config.templates_folder_id if config else '',
            'templatesFolderName': '',  # Será preenchido se necessário
            'documentsFolderId': config.library_folder_id if config else '',
            'documentsFolderName': '',  # Será preenchido se necessário
            'defaultFormat': 'pdf',
            'emailNotifications': True,
            'language': 'pt-BR'
        }
        
        # Montar connection status
        connection_status = {
            'backend': 'connected',
            'googleDrive': google_drive_status,
            'clicksign': clicksign_status,
            'lastSync': google_token.updated_at.isoformat() if google_token and google_token.updated_at else None
        }
        
        return jsonify({
            'settings': settings,
            'connectionStatus': connection_status
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting settings: {e}")
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500


@settings_bp.route('', methods=['POST'])
@flexible_hubspot_auth
@require_org
def save_settings():
    """Salva configurações da organização"""
    try:
        organization_id = g.organization_id
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Invalid request body'}), 400
        
        # Buscar ou criar configuração do Google Drive
        config = GoogleDriveConfig.query.filter_by(organization_id=organization_id).first()
        
        if not config:
            config = GoogleDriveConfig(organization_id=organization_id)
            db.session.add(config)
        
        # Atualizar configurações
        if 'templatesFolderId' in data:
            config.templates_folder_id = data['templatesFolderId']
        if 'documentsFolderId' in data:
            config.library_folder_id = data['documentsFolderId']
        
        config.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Settings saved successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error saving settings: {e}")
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500

