from flask import Blueprint, request, jsonify
from app.database import db
from app.models import GoogleOAuthToken, GoogleDriveConfig
from app.auth import require_auth
from app.utils.auth import require_org
from app.utils.hubspot_auth import flexible_hubspot_auth
from flask import g
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload, MediaIoBaseUpload
from googleapiclient.errors import HttpError
import json
import io
import base64

bp = Blueprint('google_drive', __name__, url_prefix='/api/v1/google-drive')

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
                    # Se renovação falhar, retornar None
                    print(f"Error refreshing token: {refresh_error}")
                    return None
            else:
                # Não há refresh_token para renovar
                return None
        
        return creds
    except Exception as e:
        print(f"Error getting credentials: {e}")
        return None


@bp.route('/folders', methods=['GET'])
@flexible_hubspot_auth
@require_org
def list_folders():
    """Listar pastas do Google Drive"""
    try:
        organization_id = g.organization_id
        
        creds = get_google_credentials(organization_id)
        if not creds:
            return jsonify({
                'error': 'Google account not connected or token expired'
            }), 401
        
        service = build('drive', 'v3', credentials=creds)
        
        # Buscar apenas pastas
        results = service.files().list(
            q="mimeType='application/vnd.google-apps.folder' and trashed=false",
            fields="files(id, name, parents)",
            pageSize=100
        ).execute()
        
        folders = results.get('files', [])
        
        return jsonify({
            'success': True,
            'data': folders
        }), 200
        
    except HttpError as e:
        return jsonify({
            'error': 'Google Drive API error',
            'message': str(e)
        }), 500
    except Exception as e:
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500


@bp.route('/config', methods=['POST'])
@require_org
def save_config():
    """Configurar pastas do Google Drive"""
    try:
        organization_id = g.organization_id
        data = request.get_json()
        templates_folder_id = data.get('templates_folder_id')
        library_folder_id = data.get('library_folder_id')
        
        config = GoogleDriveConfig.query.filter_by(organization_id=organization_id).first()
        
        if config:
            config.templates_folder_id = templates_folder_id
            config.library_folder_id = library_folder_id
        else:
            config = GoogleDriveConfig(
                organization_id=organization_id,
                templates_folder_id=templates_folder_id,
                library_folder_id=library_folder_id
            )
            db.session.add(config)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'data': config.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500


@bp.route('/config', methods=['GET'])
@require_org
def get_config():
    """Obter configuração de pastas"""
    try:
        organization_id = g.organization_id
        
        config = GoogleDriveConfig.query.filter_by(organization_id=organization_id).first()
        
        if not config:
            return jsonify({
                'success': True,
                'data': None
            }), 200
        
        return jsonify({
            'success': True,
            'data': config.to_dict()
        }), 200
        
    except Exception as e:
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500


@bp.route('/templates', methods=['GET'])
@require_org
def list_templates():
    """Listar templates do Google Drive"""
    try:
        organization_id = g.organization_id
        folder_id = request.args.get('folder_id')
        
        creds = get_google_credentials(organization_id)
        if not creds:
            return jsonify({
                'error': 'Google account not connected or token expired'
            }), 401
        
        service = build('drive', 'v3', credentials=creds)
        
        # Se folder_id não fornecido, usar da configuração
        if not folder_id:
            config = GoogleDriveConfig.query.filter_by(organization_id=organization_id).first()
            if config and config.templates_folder_id:
                folder_id = config.templates_folder_id
        
        # Construir query
        query = "trashed=false and (mimeType='application/pdf' or mimeType='application/vnd.google-apps.document')"
        if folder_id:
            query += f" and '{folder_id}' in parents"
        
        results = service.files().list(
            q=query,
            fields="files(id, name, mimeType, modifiedTime)",
            pageSize=100
        ).execute()
        
        files = results.get('files', [])
        
        return jsonify({
            'success': True,
            'data': files
        }), 200
        
    except HttpError as e:
        return jsonify({
            'error': 'Google Drive API error',
            'message': str(e)
        }), 500
    except Exception as e:
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500


@bp.route('/upload', methods=['POST'])
@require_org
def upload_file():
    """Upload de arquivo para Google Drive"""
    try:
        organization_id = g.organization_id
        data = request.get_json()
        file_content = data.get('file')  # base64
        folder_id = data.get('folder_id')
        filename = data.get('filename')
        
        if not file_content or not filename:
            return jsonify({
                'error': 'file and filename are required'
            }), 400
        
        creds = get_google_credentials(organization_id)
        if not creds:
            return jsonify({
                'error': 'Google account not connected or token expired'
            }), 401
        
        service = build('drive', 'v3', credentials=creds)
        
        # Decodificar base64
        file_bytes = base64.b64decode(file_content)
        file_io = io.BytesIO(file_bytes)
        
        # Metadata do arquivo
        file_metadata = {
            'name': filename
        }
        
        if folder_id:
            file_metadata['parents'] = [folder_id]
        
        media = MediaIoBaseUpload(file_io, mimetype='application/pdf', resumable=True)
        
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, name, webViewLink'
        ).execute()
        
        return jsonify({
            'success': True,
            'data': {
                'id': file.get('id'),
                'name': file.get('name'),
                'web_view_link': file.get('webViewLink')
            }
        }), 200
        
    except HttpError as e:
        return jsonify({
            'error': 'Google Drive API error',
            'message': str(e)
        }), 500
    except Exception as e:
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500

