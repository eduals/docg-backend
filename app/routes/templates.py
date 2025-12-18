from flask import Blueprint, request, jsonify, g
from app.database import db
from app.models import Template
from app.services.document_generation.google_docs import GoogleDocsService
from app.routes.google_drive_routes import get_google_credentials
from app.utils.auth import require_auth, require_org, require_admin
import logging

logger = logging.getLogger(__name__)
templates_bp = Blueprint('templates', __name__, url_prefix='/api/v1/templates')


@templates_bp.route('', methods=['GET'])
@require_auth
@require_org
def list_templates():
    """Lista templates da organização (apenas registrados no banco)"""
    org_id = g.organization_id
    file_type = request.args.get('type')  # document, presentation
    
    query = Template.query.filter_by(organization_id=org_id)
    
    if file_type:
        query = query.filter_by(google_file_type=file_type)
    
    templates = query.order_by(Template.updated_at.desc()).all()
    
    return jsonify({
        'templates': [template_to_dict(t) for t in templates]
    })


@templates_bp.route('/available', methods=['GET'])
@require_auth
@require_org
def list_available_templates():
    """
    Lista templates disponíveis de todas as fontes (Google Drive, Microsoft OneDrive, Uploaded).
    Retorna lista unificada para seleção no frontend.
    
    Query params:
    - type: document ou presentation (opcional)
    """
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from app.routes.microsoft_oauth_routes import get_microsoft_credentials
    import requests
    
    organization_id = g.organization_id
    file_type = request.args.get('type')  # document, presentation (opcional)
    
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
                        'id': None,  # Não registrado ainda
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
            
            # Filtrar apenas arquivos Word e PowerPoint
            mime_filters = []
            if not file_type or file_type == 'document':
                mime_filters.append("file/mimeType eq 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'")
            if not file_type or file_type == 'presentation':
                mime_filters.append("file/mimeType eq 'application/vnd.openxmlformats-officedocument.presentationml.presentation'")
            
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
                            'id': None,  # Não registrado ainda
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
        # Para templates enviados, verificar pelo mime_type
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
            # Buscar ID do template registrado
            registered = Template.query.filter_by(
                organization_id=organization_id,
                google_file_id=template['google_file_id']
            ).first()
            if registered:
                template['id'] = str(registered.id)
        elif template['source'] == 'microsoft' and template.get('microsoft_file_id') in registered_microsoft_ids:
            template['is_registered'] = True
            # Buscar ID do template registrado
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


@templates_bp.route('/drive', methods=['GET'])
@require_auth
@require_org
def list_templates_from_drive():
    """
    Lista templates diretamente do Google Drive sem criar registro no banco.
    Útil para selecionar templates antes de registrá-los.
    
    Query params:
    - type: document ou presentation (obrigatório)
    - folder_id: ID da pasta do Google Drive (opcional)
    """
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    
    file_type = request.args.get('type')
    folder_id = request.args.get('folder_id')
    
    if not file_type:
        return jsonify({'error': 'type é obrigatório (document ou presentation)'}), 400
    
    if file_type not in ['document', 'presentation']:
        return jsonify({'error': 'type deve ser document ou presentation'}), 400
    
    try:
        organization_id = g.organization_id
        google_creds = get_google_credentials(organization_id)
        
        if not google_creds:
            return jsonify({
                'error': 'Google account not connected or token expired'
            }), 401
        
        service = build('drive', 'v3', credentials=google_creds)
        
        # Determinar MIME type baseado no file_type
        mime_types = {
            'document': 'application/vnd.google-apps.document',
            'presentation': 'application/vnd.google-apps.presentation'
        }
        mime_type = mime_types[file_type]
        
        # Construir query
        query = f"trashed=false and mimeType='{mime_type}'"
        if folder_id:
            query += f" and '{folder_id}' in parents"
        
        # Buscar arquivos
        results = service.files().list(
            q=query,
            fields="files(id, name, mimeType, modifiedTime, createdTime, size, webViewLink)",
            pageSize=100,
            orderBy="modifiedTime desc"
        ).execute()
        
        files = results.get('files', [])
        
        # Formatar resposta
        templates = []
        for file in files:
            templates.append({
                'id': file.get('id'),
                'name': file.get('name'),
                'google_file_id': file.get('id'),
                'google_file_type': file_type,
                'google_file_url': file.get('webViewLink'),
                'modified_time': file.get('modifiedTime'),
                'created_time': file.get('createdTime'),
                'size': file.get('size'),
                'is_from_drive': True  # Flag para indicar que vem do Drive
            })
        
        return jsonify({
            'templates': templates,
            'total': len(templates)
        })
        
    except HttpError as e:
        logger.error(f"Erro ao buscar templates do Google Drive: {str(e)}")
        return jsonify({
            'error': 'Google Drive API error',
            'message': str(e)
        }), 500
    except Exception as e:
        logger.error(f"Erro ao listar templates do Drive: {str(e)}")
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500


@templates_bp.route('/<template_id>', methods=['GET'])
@require_auth
@require_org
def get_template(template_id):
    """Retorna detalhes de um template"""
    template = Template.query.filter_by(
        id=template_id,
        organization_id=g.organization_id
    ).first_or_404()
    
    return jsonify(template_to_dict(template, include_tags=True))


@templates_bp.route('/upload', methods=['POST'])
@require_auth
@require_org
def upload_template():
    """
    Upload de arquivo .doc ou .docx para usar como template.
    
    Request:
    - Content-Type: multipart/form-data
    - file: Arquivo .doc ou .docx (obrigatório)
    - name: Nome do template (opcional, usa nome do arquivo se não fornecido)
    - description: Descrição (opcional)
    
    Response:
    {
        "success": true,
        "template": {
            "id": "uuid",
            "name": "Template Name",
            "storage_file_url": "https://...",
            "storage_type": "uploaded"
        }
    }
    """
    from werkzeug.utils import secure_filename
    from app.services.storage import DigitalOceanSpacesService
    import uuid
    import os
    
    # Validar que arquivo foi enviado
    if 'file' not in request.files:
        return jsonify({'error': 'Nenhum arquivo enviado'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'Nome do arquivo vazio'}), 400
    
    # Validar tipo de arquivo
    allowed_extensions = {'.doc', '.docx'}
    file_ext = os.path.splitext(file.filename)[1].lower()
    
    if file_ext not in allowed_extensions:
        return jsonify({
            'error': f'Tipo de arquivo não permitido. Use .doc ou .docx'
        }), 400
    
    # Validar tamanho (max 10MB)
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)  # Resetar posição
    
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    if file_size > MAX_FILE_SIZE:
        return jsonify({
            'error': f'Arquivo muito grande. Tamanho máximo: 10MB'
        }), 400
    
    if file_size == 0:
        return jsonify({'error': 'Arquivo vazio'}), 400
    
    try:
        organization_id = g.organization_id
        
        # Obter nome e descrição
        template_name = request.form.get('name') or os.path.splitext(file.filename)[0]
        description = request.form.get('description')
        
        # Determinar MIME type
        mime_types = {
            '.doc': 'application/msword',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        }
        content_type = mime_types.get(file_ext, 'application/octet-stream')
        
        # Gerar nome único para o arquivo
        file_uuid = str(uuid.uuid4())
        original_filename = secure_filename(file.filename)
        filename = f"{file_uuid}{file_ext}"
        
        # Key no DigitalOcean Spaces: docg/{organization_id}/templates/{filename}
        storage_key = f"docg/{organization_id}/templates/{filename}"
        
        # Upload para DigitalOcean Spaces
        storage_service = DigitalOceanSpacesService()
        storage_url = storage_service.upload_file(file, storage_key, content_type)
        
        # Extrair tags do documento (opcional)
        detected_tags = []
        try:
            from app.services.document_generation.document_converter import DocumentConverter
            from docx import Document
            from app.services.document_generation.tag_processor import TagProcessor
            import io
            
            file.seek(0)
            file_bytes = file.read()
            
            # Normalizar documento (.doc -> .docx) se necessário
            normalized_bytes, normalized_ext = DocumentConverter.normalize_document(
                file_bytes,
                file_ext
            )
            
            # Validar estrutura do documento
            is_valid, error_message = DocumentConverter.validate_document_structure(normalized_bytes)
            if not is_valid:
                logger.warning(f"Documento pode ter problemas de estrutura: {error_message}")
                # Não falhar, apenas avisar
            
            # Processar documento normalizado
            doc = Document(io.BytesIO(normalized_bytes))
            
            # Extrair texto de todos os parágrafos
            text_content = []
            for paragraph in doc.paragraphs:
                text_content.append(paragraph.text)
            
            # Extrair tags usando TagProcessor
            all_text = ' '.join(text_content)
            detected_tags = list(set(TagProcessor.extract_tags(all_text)))
            
        except ValueError as e:
            # Erro de conversão ou validação - falhar o upload
            logger.error(f"Erro ao processar documento: {e}")
            return jsonify({
                'error': f'Não foi possível processar o arquivo: {str(e)}'
            }), 400
        except Exception as e:
            logger.warning(f"Erro ao extrair tags do documento: {e}")
            # Não falhar se não conseguir extrair tags
            detected_tags = []
        
        # Criar registro no banco
        template = Template(
            organization_id=organization_id,
            name=template_name,
            description=description,
            storage_type='uploaded',
            storage_file_url=storage_url,
            storage_file_key=storage_key,
            file_size=file_size,
            file_mime_type=content_type,
            detected_tags=detected_tags,
            created_by=g.user_id if hasattr(g, 'user_id') else None
        )
        
        db.session.add(template)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'template': template_to_dict(template, include_tags=True)
        }), 201
        
    except Exception as e:
        logger.error(f"Erro ao fazer upload de template: {str(e)}")
        db.session.rollback()
        return jsonify({
            'error': 'Erro ao fazer upload do arquivo',
            'message': str(e)
        }), 500


@templates_bp.route('', methods=['POST'])
@require_auth
@require_org
@require_admin
def create_template():
    """
    Registra um template do Google Drive ou Microsoft OneDrive.
    
    Body:
    {
        "name": "Quote Template",
        "description": "Template para cotações",
        "google_file_id": "1abc...",  // obrigatório se for Google
        "google_file_type": "document",  // document ou presentation (obrigatório se for Google)
        "microsoft_file_id": "abc123...",  // obrigatório se for Microsoft
        "microsoft_file_type": "word"  // word ou powerpoint (obrigatório se for Microsoft)
    }
    """
    data = request.get_json()
    
    # Validar que tem pelo menos Google ou Microsoft
    has_google = data.get('google_file_id') and data.get('google_file_type')
    has_microsoft = data.get('microsoft_file_id') and data.get('microsoft_file_type')
    
    if not has_google and not has_microsoft:
        return jsonify({'error': 'É necessário fornecer google_file_id/google_file_type ou microsoft_file_id/microsoft_file_type'}), 400
    
    if not data.get('name'):
        return jsonify({'error': 'name é obrigatório'}), 400
    
    # Validar tipos
    if has_google:
        if data['google_file_type'] not in ['document', 'presentation']:
            return jsonify({'error': 'google_file_type deve ser document ou presentation'}), 400
    
    if has_microsoft:
        if data['microsoft_file_type'] not in ['word', 'powerpoint']:
            return jsonify({'error': 'microsoft_file_type deve ser word ou powerpoint'}), 400
    
    # Extrair tags do template (apenas para Google por enquanto)
    detected_tags = []
    if has_google:
        try:
            organization_id = g.organization_id
            if organization_id:
                google_creds = get_google_credentials(organization_id)
                if google_creds:
                    docs_service = GoogleDocsService(google_creds)
                    detected_tags = docs_service.extract_tags_from_document(data['google_file_id'])
        except Exception as e:
            logger.warning(f"Não foi possível extrair tags: {str(e)}")
            detected_tags = []
    
    # Criar template
    template = Template(
        organization_id=g.organization_id,
        name=data['name'],
        description=data.get('description'),
        detected_tags=detected_tags,
        created_by=data.get('user_id')
    )
    
    # Configurar Google se fornecido
    if has_google:
        template.google_file_id = data['google_file_id']
        template.google_file_type = data['google_file_type']
        template.google_file_url = f"https://docs.google.com/document/d/{data['google_file_id']}/edit" if data['google_file_type'] == 'document' else f"https://docs.google.com/presentation/d/{data['google_file_id']}/edit"
        template.storage_type = 'google'
    
    # Configurar Microsoft se fornecido
    if has_microsoft:
        template.microsoft_file_id = data['microsoft_file_id']
        template.microsoft_file_type = data['microsoft_file_type']
        template.storage_type = 'microsoft'
    
    db.session.add(template)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'template': template_to_dict(template, include_tags=True)
    }), 201


@templates_bp.route('/<template_id>/tags', methods=['GET'])
@require_auth
@require_org
def get_template_tags(template_id):
    """
    Retorna tags detectadas no template.
    
    Retorna tags no formato:
    {
        "tags": [
            {
                "tag": "{{deal.dealname}}",
                "type": "hubspot",
                "object_type": "deal",
                "property": "dealname"
            },
            {
                "tag": "{{ai:summary}}",
                "type": "ai",
                "ai_tag": "summary"
            }
        ]
    }
    """
    template = Template.query.filter_by(
        id=template_id,
        organization_id=g.organization_id
    ).first_or_404()
    
    from app.services.document_generation.tag_processor import TagProcessor
    
    detected_tags = template.detected_tags or []
    
    # Processar tags para formato estruturado
    tags = []
    for tag_str in detected_tags:
        tag_info = {
            'tag': f'{{{{{tag_str}}}}}',
            'type': 'hubspot',
            'object_type': None,
            'property': None
        }
        
        # Verificar se é tag AI
        if tag_str.startswith('ai:'):
            tag_info['type'] = 'ai'
            tag_info['ai_tag'] = tag_str.replace('ai:', '')
        else:
            # Tentar extrair object_type e property
            parts = tag_str.split('.')
            if len(parts) >= 2:
                tag_info['object_type'] = parts[0]
                tag_info['property'] = '.'.join(parts[1:])
            else:
                tag_info['property'] = tag_str
        
        tags.append(tag_info)
    
    return jsonify({
        'tags': tags
    })


@templates_bp.route('/<template_id>/sync', methods=['POST'])
@require_auth
@require_org
@require_admin
def sync_template(template_id):
    """
    Sincroniza template do Google Drive ou Microsoft OneDrive.
    Re-analisa o template e atualiza as tags detectadas.
    """
    template = Template.query.filter_by(
        id=template_id,
        organization_id=g.organization_id
    ).first_or_404()
    
    try:
        organization_id = g.organization_id
        
        # Verificar se é template do Google Drive
        if not template.google_file_id:
            return jsonify({'error': 'Sincronização de templates Microsoft ainda não implementada'}), 400
        
        google_creds = get_google_credentials(organization_id)
        if not google_creds:
            return jsonify({'error': 'Credenciais do Google não configuradas'}), 400
        
        docs_service = GoogleDocsService(google_creds)
        
        # Extrair tags do documento
        detected_tags = docs_service.extract_tags_from_document(template.google_file_id)
        
        # Extrair tags AI também
        from app.services.document_generation.tag_processor import TagProcessor
        # Buscar conteúdo do documento para extrair tags AI
        # Por enquanto, vamos apenas atualizar as tags normais
        # TODO: Extrair tags AI do conteúdo do documento
        
        template.detected_tags = detected_tags
        template.version += 1
        template.last_synced_at = db.func.now()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'detected_tags': detected_tags,
            'version': template.version
        })
        
    except Exception as e:
        logger.error(f"Erro ao sincronizar template: {str(e)}")
        return jsonify({'error': str(e)}), 500


@templates_bp.route('/<template_id>/sync-tags', methods=['POST'])
@require_auth
@require_org
@require_admin
def sync_template_tags(template_id):
    """Alias para /sync (mantido para compatibilidade)"""
    return sync_template(template_id)


@templates_bp.route('/<template_id>', methods=['PUT'])
@require_auth
@require_org
@require_admin
def update_template(template_id):
    """Atualiza um template (nome e descrição)"""
    template = Template.query.filter_by(
        id=template_id,
        organization_id=g.organization_id
    ).first_or_404()
    
    data = request.get_json()
    
    if 'name' in data:
        if not data['name'] or not data['name'].strip():
            return jsonify({'error': 'name não pode ser vazio'}), 400
        template.name = data['name'].strip()
    
    if 'description' in data:
        template.description = data['description'] if data['description'] else None
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'template': template_to_dict(template, include_tags=False)
    })


@templates_bp.route('/<template_id>/open-editor', methods=['POST'])
@require_auth
@require_org
def open_editor(template_id):
    """
    Retorna URL para abrir o template no editor apropriado.
    
    Response:
    {
        "success": true,
        "editor_url": "https://...",
        "editor_type": "google|microsoft|uploaded"
    }
    """
    from app.services.storage import DigitalOceanSpacesService
    
    template = Template.query.filter_by(
        id=template_id,
        organization_id=g.organization_id
    ).first_or_404()
    
    editor_url = None
    editor_type = None
    
    # Determinar tipo de template e URL apropriada
    if template.storage_type == 'google' or template.google_file_id:
        # Template do Google Docs
        if template.google_file_type == 'document':
            editor_url = f"https://docs.google.com/document/d/{template.google_file_id}/edit"
        elif template.google_file_type == 'presentation':
            editor_url = f"https://docs.google.com/presentation/d/{template.google_file_id}/edit"
        else:
            editor_url = template.google_file_url or f"https://docs.google.com/document/d/{template.google_file_id}/edit"
        editor_type = 'google'
        
    elif template.storage_type == 'microsoft' or template.microsoft_file_id:
        # Template do Microsoft Word/PowerPoint
        editor_url = f"https://office.com/m/{template.microsoft_file_type}/viewer/action/view?resid={template.microsoft_file_id}"
        editor_type = 'microsoft'
        
    elif template.storage_type == 'uploaded' or template.storage_file_key:
        # Template enviado - gerar URL assinada temporária
        storage_service = DigitalOceanSpacesService()
        editor_url = storage_service.generate_signed_url(
            template.storage_file_key,
            expiration=3600  # 1 hora
        )
        editor_type = 'uploaded'
        
    else:
        return jsonify({
            'error': 'Template não possui URL de editor disponível'
        }), 400
    
    return jsonify({
        'success': True,
        'editor_url': editor_url,
        'editor_type': editor_type
    })


@templates_bp.route('/<template_id>', methods=['DELETE'])
@require_auth
@require_org
@require_admin
def delete_template(template_id):
    """Deleta um template"""
    from app.services.storage import DigitalOceanSpacesService
    
    template = Template.query.filter_by(
        id=template_id,
        organization_id=g.organization_id
    ).first_or_404()
    
    # Verificar se tem workflows usando
    if template.workflows.count() > 0:
        return jsonify({
            'error': 'Template está sendo usado por workflows. Remova os workflows primeiro.'
        }), 400
    
    # Se for template enviado, deletar do DigitalOcean Spaces também
    if template.storage_type == 'uploaded' and template.storage_file_key:
        try:
            storage_service = DigitalOceanSpacesService()
            storage_service.delete_file(template.storage_file_key)
        except Exception as e:
            logger.warning(f"Erro ao deletar arquivo do Spaces: {str(e)}")
            # Continuar mesmo se falhar deletar do Spaces
    
    db.session.delete(template)
    db.session.commit()
    
    return jsonify({'success': True})


def template_to_dict(template: Template, include_tags: bool = False) -> dict:
    """Converte template para dicionário"""
    result = {
        'id': str(template.id),
        'name': template.name,
        'description': template.description,
        'google_file_id': template.google_file_id,
        'google_file_type': template.google_file_type,
        'google_file_url': template.google_file_url,
        'microsoft_file_id': template.microsoft_file_id,
        'microsoft_file_type': template.microsoft_file_type,
        'thumbnail_url': template.thumbnail_url,
        'version': template.version,
        'created_at': template.created_at.isoformat() if template.created_at else None,
        'updated_at': template.updated_at.isoformat() if template.updated_at else None,
        'storage_type': template.storage_type,
        'storage_file_url': template.storage_file_url,
        'storage_file_key': template.storage_file_key,
        'file_size': template.file_size,
        'file_mime_type': template.file_mime_type
    }
    
    if include_tags:
        result['detected_tags'] = template.detected_tags or []
    
    return result

