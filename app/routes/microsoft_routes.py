from flask import Blueprint, request, jsonify, g
from app.utils.auth import require_auth, require_org
from app.routes.microsoft_oauth_routes import get_microsoft_credentials
import requests
import logging

logger = logging.getLogger(__name__)
microsoft_bp = Blueprint('microsoft', __name__, url_prefix='/api/v1/microsoft')


@microsoft_bp.route('/folders', methods=['GET'])
@require_auth
@require_org
def list_folders():
    """Lista pastas do OneDrive (root ou pasta específica)"""
    try:
        organization_id = g.organization_id
        folder_id = request.args.get('folder_id')
        
        credentials = get_microsoft_credentials(str(organization_id))
        if not credentials:
            return jsonify({
                'error': 'Microsoft account not connected or token expired'
            }), 401
        
        access_token = credentials.get('access_token')
        if not access_token:
            return jsonify({
                'error': 'Microsoft access token not available'
            }), 401
        
        # Construir URL baseado se é root ou pasta específica
        if folder_id:
            url = f'https://graph.microsoft.com/v1.0/me/drive/items/{folder_id}/children'
        else:
            url = 'https://graph.microsoft.com/v1.0/me/drive/root/children'
        
        # Filtrar apenas pastas
        params = {
            '$filter': "folder ne null",
            '$select': 'id,name,folder,parentReference'
        }
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json'
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        folders = []
        
        for item in data.get('value', []):
            if 'folder' in item:  # Garantir que é uma pasta
                folders.append({
                    'id': item.get('id'),
                    'name': item.get('name'),
                    'parent_id': item.get('parentReference', {}).get('id') if item.get('parentReference') else None
                })
        
        return jsonify({
            'success': True,
            'data': folders
        }), 200
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Microsoft Graph API error: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                return jsonify({
                    'error': 'Microsoft Graph API error',
                    'message': error_data.get('error', {}).get('message', str(e))
                }), e.response.status_code
            except:
                return jsonify({
                    'error': 'Microsoft Graph API error',
                    'message': str(e)
                }), e.response.status_code if hasattr(e, 'response') else 500
        return jsonify({
            'error': 'Microsoft Graph API error',
            'message': str(e)
        }), 500
    except Exception as e:
        logger.error(f"Error listing Microsoft folders: {str(e)}")
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500


@microsoft_bp.route('/folders/<folder_id>/children', methods=['GET'])
@require_auth
@require_org
def list_folder_children(folder_id):
    """Lista arquivos e pastas dentro de uma pasta específica"""
    try:
        organization_id = g.organization_id
        
        credentials = get_microsoft_credentials(str(organization_id))
        if not credentials:
            return jsonify({
                'error': 'Microsoft account not connected or token expired'
            }), 401
        
        access_token = credentials.get('access_token')
        if not access_token:
            return jsonify({
                'error': 'Microsoft access token not available'
            }), 401
        
        url = f'https://graph.microsoft.com/v1.0/me/drive/items/{folder_id}/children'
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        items = []
        
        for item in data.get('value', []):
            item_data = {
                'id': item.get('id'),
                'name': item.get('name'),
                'mimeType': item.get('file', {}).get('mimeType') if 'file' in item else None,
                'is_folder': 'folder' in item,
                'lastModifiedDateTime': item.get('lastModifiedDateTime'),
                'webUrl': item.get('webUrl')
            }
            
            # Se for pasta, adicionar parent_id
            if 'folder' in item:
                item_data['parent_id'] = item.get('parentReference', {}).get('id') if item.get('parentReference') else None
            
            items.append(item_data)
        
        return jsonify({
            'success': True,
            'data': items
        }), 200
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Microsoft Graph API error: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                return jsonify({
                    'error': 'Microsoft Graph API error',
                    'message': error_data.get('error', {}).get('message', str(e))
                }), e.response.status_code
            except:
                return jsonify({
                    'error': 'Microsoft Graph API error',
                    'message': str(e)
                }), e.response.status_code if hasattr(e, 'response') else 500
        return jsonify({
            'error': 'Microsoft Graph API error',
            'message': str(e)
        }), 500
    except Exception as e:
        logger.error(f"Error listing Microsoft folder children: {str(e)}")
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500


@microsoft_bp.route('/files', methods=['GET'])
@require_auth
@require_org
def list_files():
    """Lista arquivos Word/PowerPoint do OneDrive (root ou pasta específica)"""
    try:
        organization_id = g.organization_id
        folder_id = request.args.get('folder_id')
        
        credentials = get_microsoft_credentials(str(organization_id))
        if not credentials:
            return jsonify({
                'error': 'Microsoft account not connected or token expired'
            }), 401
        
        access_token = credentials.get('access_token')
        if not access_token:
            return jsonify({
                'error': 'Microsoft access token not available'
            }), 401
        
        # Construir URL baseado se é root ou pasta específica
        if folder_id:
            url = f'https://graph.microsoft.com/v1.0/me/drive/items/{folder_id}/children'
        else:
            url = 'https://graph.microsoft.com/v1.0/me/drive/root/children'
        
        # Filtrar apenas arquivos Word e PowerPoint
        # Word: application/vnd.openxmlformats-officedocument.wordprocessingml.document
        # PowerPoint: application/vnd.openxmlformats-officedocument.presentationml.presentation
        params = {
            '$filter': "file ne null and (file/mimeType eq 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' or file/mimeType eq 'application/vnd.openxmlformats-officedocument.presentationml.presentation')",
            '$select': 'id,name,file,lastModifiedDateTime,webUrl'
        }
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json'
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        files = []
        
        for item in data.get('value', []):
            mime_type = item.get('file', {}).get('mimeType', '')
            file_type = None
            
            if 'wordprocessingml' in mime_type:
                file_type = 'word'
            elif 'presentationml' in mime_type:
                file_type = 'powerpoint'
            
            if file_type:
                files.append({
                    'id': item.get('id'),
                    'name': item.get('name'),
                    'mimeType': mime_type,
                    'file_type': file_type,
                    'lastModifiedDateTime': item.get('lastModifiedDateTime'),
                    'webUrl': item.get('webUrl')
                })
        
        return jsonify({
            'success': True,
            'data': files
        }), 200
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Microsoft Graph API error: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                return jsonify({
                    'error': 'Microsoft Graph API error',
                    'message': error_data.get('error', {}).get('message', str(e))
                }), e.response.status_code
            except:
                return jsonify({
                    'error': 'Microsoft Graph API error',
                    'message': str(e)
                }), e.response.status_code if hasattr(e, 'response') else 500
        return jsonify({
            'error': 'Microsoft Graph API error',
            'message': str(e)
        }), 500
    except Exception as e:
        logger.error(f"Error listing Microsoft files: {str(e)}")
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500

