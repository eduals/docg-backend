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
    """Lista templates da organização"""
    org_id = g.organization_id
    file_type = request.args.get('type')  # document, presentation
    
    query = Template.query.filter_by(organization_id=org_id)
    
    if file_type:
        query = query.filter_by(google_file_type=file_type)
    
    templates = query.order_by(Template.updated_at.desc()).all()
    
    return jsonify({
        'templates': [template_to_dict(t) for t in templates]
    })


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
    
    # Configurar Microsoft se fornecido
    if has_microsoft:
        template.microsoft_file_id = data['microsoft_file_id']
        template.microsoft_file_type = data['microsoft_file_type']
    
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


@templates_bp.route('/<template_id>', methods=['DELETE'])
@require_auth
@require_org
@require_admin
def delete_template(template_id):
    """Deleta um template"""
    template = Template.query.filter_by(
        id=template_id,
        organization_id=g.organization_id
    ).first_or_404()
    
    # Verificar se tem workflows usando
    if template.workflows.count() > 0:
        return jsonify({
            'error': 'Template está sendo usado por workflows. Remova os workflows primeiro.'
        }), 400
    
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
        'updated_at': template.updated_at.isoformat() if template.updated_at else None
    }
    
    if include_tags:
        result['detected_tags'] = template.detected_tags or []
    
    return result

