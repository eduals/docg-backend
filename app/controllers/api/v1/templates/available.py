"""
List Available Templates Controller.
"""

from flask import request, jsonify, g
from app.database import db
from app.models import Template
from app.routes.google_drive_routes import get_google_credentials
import logging

logger = logging.getLogger(__name__)


def list_available_templates():
    """
    Lista templates disponíveis de todas as fontes (Google Drive, Microsoft OneDrive, Uploaded).
    Retorna lista unificada para seleção no frontend.

    Query params:
    - type: document ou presentation (opcional)
    """
    from googleapiclient.discovery import build
    from app.routes.microsoft_oauth_routes import get_microsoft_credentials
    import requests

    organization_id = g.organization_id
    file_type = request.args.get('type')

    templates = []
    google_connected = False
    microsoft_connected = False

    # 1. Buscar templates do Google Drive (se conectado)
    try:
        google_creds = get_google_credentials(organization_id)
        if google_creds:
            google_connected = True
            service = build('drive', 'v3', credentials=google_creds)

            # Determinar MIME types baseado no file_type
            mime_types = []
            if not file_type or file_type == 'document':
                mime_types.append('application/vnd.google-apps.document')
            if not file_type or file_type == 'presentation':
                mime_types.append('application/vnd.google-apps.presentation')

            for mime_type in mime_types:
                query = f"trashed=false and mimeType='{mime_type}'"
                results = service.files().list(
                    q=query,
                    fields="files(id, name, mimeType, modifiedTime, createdTime, size, webViewLink)",
                    pageSize=100,
                    orderBy="modifiedTime desc"
                ).execute()

                for file in results.get('files', []):
                    file_type_str = 'document' if 'document' in mime_type else 'presentation'
                    templates.append({
                        'id': None,
                        'name': file.get('name'),
                        'source': 'google',
                        'google_file_id': file.get('id'),
                        'google_file_type': file_type_str,
                        'google_file_url': file.get('webViewLink'),
                        'modified_time': file.get('modifiedTime'),
                        'created_time': file.get('createdTime'),
                        'size': file.get('size'),
                        'is_registered': False,
                        'storage_type': 'google'
                    })
    except Exception as e:
        logger.warning(f"Erro ao buscar templates do Google Drive: {str(e)}")

    # 2. Buscar templates do Microsoft OneDrive (se conectado)
    try:
        microsoft_creds = get_microsoft_credentials(str(organization_id))
        if microsoft_creds and microsoft_creds.get('access_token'):
            microsoft_connected = True

            access_token = microsoft_creds.get('access_token')
            url = 'https://graph.microsoft.com/v1.0/me/drive/root/children'

            mime_filters = []
            if not file_type or file_type == 'document':
                mime_filters.append(
                    "file/mimeType eq 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'"
                )
            if not file_type or file_type == 'presentation':
                mime_filters.append(
                    "file/mimeType eq 'application/vnd.openxmlformats-officedocument.presentationml.presentation'"
                )

            if mime_filters:
                params = {
                    '$filter': f"file ne null and ({' or '.join(mime_filters)})",
                    '$select': 'id,name,file,lastModifiedDateTime,webUrl'
                }

                headers = {
                    'Authorization': f'Bearer {access_token}',
                    'Accept': 'application/json'
                }

                response = requests.get(url, headers=headers, params=params, timeout=10)
                response.raise_for_status()

                data = response.json()
                for item in data.get('value', []):
                    mime_type = item.get('file', {}).get('mimeType', '')
                    file_type_str = None

                    if 'wordprocessingml' in mime_type:
                        file_type_str = 'word'
                    elif 'presentationml' in mime_type:
                        file_type_str = 'powerpoint'

                    if file_type_str:
                        templates.append({
                            'id': None,
                            'name': item.get('name'),
                            'source': 'microsoft',
                            'microsoft_file_id': item.get('id'),
                            'microsoft_file_type': file_type_str,
                            'microsoft_file_url': item.get('webUrl'),
                            'modified_time': item.get('lastModifiedDateTime'),
                            'is_registered': False,
                            'storage_type': 'microsoft'
                        })
    except Exception as e:
        logger.warning(f"Erro ao buscar templates do Microsoft OneDrive: {str(e)}")

    # 3. Buscar templates enviados (registrados no banco)
    query = Template.query.filter_by(organization_id=organization_id)
    if file_type:
        if file_type == 'document':
            query = query.filter(
                db.or_(
                    Template.file_mime_type.like('%word%'),
                    Template.file_mime_type.like('%msword%')
                )
            )
        elif file_type == 'presentation':
            query = query.filter(
                Template.file_mime_type.like('%presentation%')
            )

    uploaded_templates = query.filter(Template.storage_type == 'uploaded').all()

    for template in uploaded_templates:
        templates.append({
            'id': str(template.id),
            'name': template.name,
            'source': 'uploaded',
            'storage_file_url': template.storage_file_url,
            'storage_file_key': template.storage_file_key,
            'file_size': template.file_size,
            'file_mime_type': template.file_mime_type,
            'modified_time': template.updated_at.isoformat() if template.updated_at else None,
            'created_time': template.created_at.isoformat() if template.created_at else None,
            'is_registered': True,
            'storage_type': 'uploaded'
        })

    # 4. Marcar templates registrados (Google e Microsoft que já estão no banco)
    registered_google_ids = set()
    registered_microsoft_ids = set()

    registered_templates = Template.query.filter_by(organization_id=organization_id).all()
    for t in registered_templates:
        if t.google_file_id:
            registered_google_ids.add(t.google_file_id)
        if t.microsoft_file_id:
            registered_microsoft_ids.add(t.microsoft_file_id)

    for template in templates:
        if template['source'] == 'google' and template.get('google_file_id') in registered_google_ids:
            template['is_registered'] = True
            registered = Template.query.filter_by(
                organization_id=organization_id,
                google_file_id=template['google_file_id']
            ).first()
            if registered:
                template['id'] = str(registered.id)
        elif template['source'] == 'microsoft' and template.get('microsoft_file_id') in registered_microsoft_ids:
            template['is_registered'] = True
            registered = Template.query.filter_by(
                organization_id=organization_id,
                microsoft_file_id=template['microsoft_file_id']
            ).first()
            if registered:
                template['id'] = str(registered.id)

    return jsonify({
        'templates': templates,
        'sources': {
            'google_connected': google_connected,
            'microsoft_connected': microsoft_connected
        },
        'total': len(templates)
    })
