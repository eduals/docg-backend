from flask import Blueprint, request, jsonify, g
from app.database import db
from app.models import Workflow, WorkflowFieldMapping, Template, AIGenerationMapping, DataSourceConnection
from app.utils.auth import require_auth, require_org, require_admin
from app.utils.hubspot_auth import flexible_hubspot_auth
import logging

logger = logging.getLogger(__name__)
workflows_bp = Blueprint('workflows', __name__, url_prefix='/api/v1/workflows')

# Provedores de IA suportados
AI_PROVIDERS = ['openai', 'gemini', 'anthropic']


def validate_post_actions(post_actions):
    """
    Valida a estrutura de post_actions.
    
    Args:
        post_actions: Dict com configurações de post_actions
    
    Returns:
        Tuple (is_valid, error_message)
    """
    if not post_actions or not isinstance(post_actions, dict):
        return True, None  # post_actions é opcional
    
    hubspot_config = post_actions.get('hubspot_attachment')
    if not hubspot_config:
        return True, None  # Não há configuração HubSpot, tudo OK
    
    if not isinstance(hubspot_config, dict):
        return False, 'hubspot_attachment deve ser um objeto'
    
    # Validar enabled
    if 'enabled' in hubspot_config and not isinstance(hubspot_config['enabled'], bool):
        return False, 'hubspot_attachment.enabled deve ser um booleano'
    
    # Se enabled, validar attachment_type
    if hubspot_config.get('enabled'):
        attachment_type = hubspot_config.get('attachment_type', 'engagement')
        if attachment_type not in ['engagement', 'property']:
            return False, 'hubspot_attachment.attachment_type deve ser "engagement" ou "property"'
        
        # Se attachment_type é 'property', property_name é obrigatório
        if attachment_type == 'property':
            if not hubspot_config.get('property_name'):
                return False, 'hubspot_attachment.property_name é obrigatório quando attachment_type é "property"'
    
    return True, None


@workflows_bp.route('', methods=['GET'])
@flexible_hubspot_auth
@require_org
def list_workflows():
    """Lista workflows da organização"""
    org_id = g.organization_id
    status = request.args.get('status')
    
    query = Workflow.query.filter_by(organization_id=org_id)
    
    if status:
        query = query.filter_by(status=status)
    
    workflows = query.order_by(Workflow.updated_at.desc()).all()
    
    return jsonify({
        'workflows': [workflow_to_dict(w) for w in workflows]
    })


@workflows_bp.route('/<workflow_id>', methods=['GET'])
@require_auth
@require_org
def get_workflow(workflow_id):
    """Retorna detalhes de um workflow"""
    workflow = Workflow.query.filter_by(
        id=workflow_id,
        organization_id=g.organization_id
    ).first_or_404()
    
    return jsonify(workflow_to_dict(workflow, include_mappings=True))


@workflows_bp.route('', methods=['POST'])
@require_auth
@require_org
@require_admin
def create_workflow():
    """
    Cria um novo workflow.
    
    Body:
    {
        "name": "Quote Generator",
        "description": "...",
        "source_connection_id": "uuid",
        "source_object_type": "deal",
        "template_id": "uuid",
        "output_folder_id": "google_drive_folder_id",
        "output_name_template": "{{company_name}} - Quote - {{date}}",
        "create_pdf": true,
        "trigger_type": "manual",
        "field_mappings": [
            {"template_tag": "company_name", "source_field": "associations.company.name"},
            {"template_tag": "deal_amount", "source_field": "amount", "transform_type": "currency"}
        ]
    }
    """
    data = request.get_json()
    
    # Validações
    required = ['name', 'template_id']
    for field in required:
        if not data.get(field):
            return jsonify({'error': f'{field} é obrigatório'}), 400
    
    # Validar post_actions se fornecido
    post_actions = data.get('post_actions')
    if post_actions:
        is_valid, error_msg = validate_post_actions(post_actions)
        if not is_valid:
            return jsonify({'error': error_msg}), 400
    
    # Criar workflow
    workflow = Workflow(
        organization_id=g.organization_id,
        name=data['name'],
        description=data.get('description'),
        source_connection_id=data.get('source_connection_id'),
        source_object_type=data.get('source_object_type'),
        source_config=data.get('source_config'),
        template_id=data['template_id'],
        output_folder_id=data.get('output_folder_id'),
        output_name_template=data.get('output_name_template', '{{object_type}} - {{timestamp}}'),
        create_pdf=data.get('create_pdf', True),
        trigger_type=data.get('trigger_type', 'manual'),
        trigger_config=data.get('trigger_config'),
        post_actions=data.get('post_actions'),
        status='draft',
        created_by=data.get('user_id')
    )
    
    db.session.add(workflow)
    db.session.flush()  # Para obter o ID
    
    # Criar field mappings
    for mapping_data in data.get('field_mappings', []):
        mapping = WorkflowFieldMapping(
            workflow_id=workflow.id,
            template_tag=mapping_data['template_tag'],
            source_field=mapping_data['source_field'],
            transform_type=mapping_data.get('transform_type'),
            transform_config=mapping_data.get('transform_config'),
            default_value=mapping_data.get('default_value')
        )
        db.session.add(mapping)
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'workflow': workflow_to_dict(workflow, include_mappings=True)
    }), 201


@workflows_bp.route('/<workflow_id>', methods=['PUT'])
@require_auth
@require_org
@require_admin
def update_workflow(workflow_id):
    """Atualiza um workflow"""
    workflow = Workflow.query.filter_by(
        id=workflow_id,
        organization_id=g.organization_id
    ).first_or_404()
    
    data = request.get_json()
    
    # Validar post_actions se fornecido
    if 'post_actions' in data:
        is_valid, error_msg = validate_post_actions(data['post_actions'])
        if not is_valid:
            return jsonify({'error': error_msg}), 400
    
    # Atualizar campos permitidos
    allowed_fields = [
        'name', 'description', 'source_connection_id', 'source_object_type',
        'source_config', 'template_id', 'output_folder_id', 'output_name_template',
        'create_pdf', 'trigger_type', 'trigger_config', 'post_actions', 'status'
    ]
    
    for field in allowed_fields:
        if field in data:
            setattr(workflow, field, data[field])
    
    # Atualizar field mappings se fornecidos
    if 'field_mappings' in data:
        # Remove mapeamentos existentes
        WorkflowFieldMapping.query.filter_by(workflow_id=workflow.id).delete()
        
        # Cria novos
        for mapping_data in data['field_mappings']:
            mapping = WorkflowFieldMapping(
                workflow_id=workflow.id,
                template_tag=mapping_data['template_tag'],
                source_field=mapping_data['source_field'],
                transform_type=mapping_data.get('transform_type'),
                transform_config=mapping_data.get('transform_config'),
                default_value=mapping_data.get('default_value')
            )
            db.session.add(mapping)
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'workflow': workflow_to_dict(workflow, include_mappings=True)
    })


@workflows_bp.route('/<workflow_id>', methods=['DELETE'])
@require_auth
@require_org
@require_admin
def delete_workflow(workflow_id):
    """Deleta um workflow"""
    workflow = Workflow.query.filter_by(
        id=workflow_id,
        organization_id=g.organization_id
    ).first_or_404()
    
    db.session.delete(workflow)
    db.session.commit()
    
    return jsonify({'success': True})


@workflows_bp.route('/<workflow_id>/activate', methods=['POST'])
@require_auth
@require_org
@require_admin
def activate_workflow(workflow_id):
    """Ativa um workflow"""
    workflow = Workflow.query.filter_by(
        id=workflow_id,
        organization_id=g.organization_id
    ).first_or_404()
    
    # Validar que workflow está completo
    if not workflow.template_id:
        return jsonify({'error': 'Template não configurado'}), 400
    
    workflow.status = 'active'
    db.session.commit()
    
    return jsonify({
        'success': True,
        'workflow': workflow_to_dict(workflow)
    })


def workflow_to_dict(workflow: Workflow, include_mappings: bool = False, include_ai_mappings: bool = False) -> dict:
    """Converte workflow para dicionário"""
    result = {
        'id': str(workflow.id),
        'name': workflow.name,
        'description': workflow.description,
        'status': workflow.status,
        'source_connection_id': str(workflow.source_connection_id) if workflow.source_connection_id else None,
        'source_object_type': workflow.source_object_type,
        'template_id': str(workflow.template_id) if workflow.template_id else None,
        'output_folder_id': workflow.output_folder_id,
        'output_name_template': workflow.output_name_template,
        'create_pdf': workflow.create_pdf,
        'trigger_type': workflow.trigger_type,
        'post_actions': workflow.post_actions,
        'created_at': workflow.created_at.isoformat(),
        'updated_at': workflow.updated_at.isoformat()
    }
    
    if include_mappings:
        result['field_mappings'] = [
            {
                'id': str(m.id),
                'template_tag': m.template_tag,
                'source_field': m.source_field,
                'transform_type': m.transform_type,
                'transform_config': m.transform_config,
                'default_value': m.default_value
            }
            for m in workflow.field_mappings
        ]
    
    if include_ai_mappings:
        result['ai_mappings'] = [m.to_dict() for m in workflow.ai_mappings]
    
    # Incluir info do template se disponível
    if workflow.template:
        result['template'] = {
            'id': str(workflow.template.id),
            'name': workflow.template.name,
            'google_file_type': workflow.template.google_file_type,
            'thumbnail_url': workflow.template.thumbnail_url
        }
    
    return result


# ==================== AI MAPPING ENDPOINTS ====================

@workflows_bp.route('/<workflow_id>/ai-mappings', methods=['GET'])
@require_auth
@require_org
def list_ai_mappings(workflow_id):
    """Lista mapeamentos de IA de um workflow"""
    import uuid
    
    # Converter workflow_id para UUID se for string
    workflow_id_uuid = uuid.UUID(workflow_id) if isinstance(workflow_id, str) else workflow_id
    
    # Converter organization_id para UUID se for string
    org_id = uuid.UUID(g.organization_id) if isinstance(g.organization_id, str) else g.organization_id
    
    workflow = Workflow.query.filter_by(
        id=workflow_id_uuid,
        organization_id=org_id
    ).first_or_404()
    
    mappings = AIGenerationMapping.query.filter_by(
        workflow_id=workflow.id
    ).order_by(AIGenerationMapping.created_at.desc()).all()
    
    return jsonify({
        'ai_mappings': [m.to_dict() for m in mappings]
    })


@workflows_bp.route('/<workflow_id>/ai-mappings', methods=['POST'])
@require_auth
@require_org
@require_admin
def create_ai_mapping(workflow_id):
    """
    Cria um novo mapeamento de IA para o workflow.
    
    Body:
    {
        "ai_tag": "paragrapho1",
        "source_fields": ["dealname", "amount", "company.name"],
        "provider": "openai",
        "model": "gpt-4",
        "ai_connection_id": "uuid",
        "prompt_template": "Gere um parágrafo descrevendo o deal {{dealname}}...",
        "temperature": 0.7,
        "max_tokens": 500,
        "fallback_value": "[Texto não gerado]"
    }
    """
    workflow = Workflow.query.filter_by(
        id=workflow_id,
        organization_id=g.organization_id
    ).first_or_404()
    
    data = request.get_json()
    
    # Validações
    required = ['ai_tag', 'provider', 'model']
    for field in required:
        if not data.get(field):
            return jsonify({'error': f'{field} é obrigatório'}), 400
    
    # Validar provider
    provider = data['provider'].lower()
    if provider not in AI_PROVIDERS:
        return jsonify({
            'error': f'Provedor não suportado. Use: {", ".join(AI_PROVIDERS)}'
        }), 400
    
    # Validar ai_connection_id se fornecido
    ai_connection_id = data.get('ai_connection_id')
    if ai_connection_id:
        connection = DataSourceConnection.query.filter_by(
            id=ai_connection_id,
            organization_id=g.organization_id,
            source_type=provider
        ).first()
        if not connection:
            return jsonify({
                'error': 'Conexão de IA não encontrada ou não corresponde ao provider'
            }), 400
    
    # Verificar se tag já existe no workflow
    existing = AIGenerationMapping.query.filter_by(
        workflow_id=workflow.id,
        ai_tag=data['ai_tag']
    ).first()
    
    if existing:
        return jsonify({
            'error': f'Tag AI "{data["ai_tag"]}" já existe neste workflow'
        }), 409
    
    # Criar mapeamento
    mapping = AIGenerationMapping(
        workflow_id=workflow.id,
        ai_tag=data['ai_tag'],
        source_fields=data.get('source_fields', []),
        provider=provider,
        model=data['model'],
        ai_connection_id=ai_connection_id,
        prompt_template=data.get('prompt_template'),
        temperature=data.get('temperature', 0.7),
        max_tokens=data.get('max_tokens', 1000),
        fallback_value=data.get('fallback_value')
    )
    
    db.session.add(mapping)
    db.session.commit()
    
    logger.info(f"AI mapping criado: workflow={workflow_id}, tag={data['ai_tag']}")
    
    return jsonify({
        'success': True,
        'ai_mapping': mapping.to_dict()
    }), 201


@workflows_bp.route('/<workflow_id>/ai-mappings/<mapping_id>', methods=['GET'])
@require_auth
@require_org
def get_ai_mapping(workflow_id, mapping_id):
    """Retorna detalhes de um mapeamento de IA"""
    workflow = Workflow.query.filter_by(
        id=workflow_id,
        organization_id=g.organization_id
    ).first_or_404()
    
    mapping = AIGenerationMapping.query.filter_by(
        id=mapping_id,
        workflow_id=workflow.id
    ).first_or_404()
    
    return jsonify(mapping.to_dict())


@workflows_bp.route('/<workflow_id>/ai-mappings/<mapping_id>', methods=['PATCH'])
@require_auth
@require_org
@require_admin
def update_ai_mapping(workflow_id, mapping_id):
    """
    Atualiza um mapeamento de IA.
    
    Body (todos opcionais):
    {
        "source_fields": [...],
        "provider": "gemini",
        "model": "gemini-1.5-pro",
        "ai_connection_id": "uuid",
        "prompt_template": "...",
        "temperature": 0.5,
        "max_tokens": 800,
        "fallback_value": "..."
    }
    """
    workflow = Workflow.query.filter_by(
        id=workflow_id,
        organization_id=g.organization_id
    ).first_or_404()
    
    mapping = AIGenerationMapping.query.filter_by(
        id=mapping_id,
        workflow_id=workflow.id
    ).first_or_404()
    
    data = request.get_json()
    
    # Atualizar campos permitidos
    if 'source_fields' in data:
        mapping.source_fields = data['source_fields']
    
    if 'provider' in data:
        provider = data['provider'].lower()
        if provider not in AI_PROVIDERS:
            return jsonify({
                'error': f'Provedor não suportado. Use: {", ".join(AI_PROVIDERS)}'
            }), 400
        mapping.provider = provider
    
    if 'model' in data:
        mapping.model = data['model']
    
    if 'ai_connection_id' in data:
        ai_connection_id = data['ai_connection_id']
        if ai_connection_id:
            connection = DataSourceConnection.query.filter_by(
                id=ai_connection_id,
                organization_id=g.organization_id
            ).first()
            if not connection:
                return jsonify({'error': 'Conexão de IA não encontrada'}), 400
        mapping.ai_connection_id = ai_connection_id
    
    if 'prompt_template' in data:
        mapping.prompt_template = data['prompt_template']
    
    if 'temperature' in data:
        mapping.temperature = data['temperature']
    
    if 'max_tokens' in data:
        mapping.max_tokens = data['max_tokens']
    
    if 'fallback_value' in data:
        mapping.fallback_value = data['fallback_value']
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'ai_mapping': mapping.to_dict()
    })


@workflows_bp.route('/<workflow_id>/ai-mappings/<mapping_id>', methods=['DELETE'])
@require_auth
@require_org
@require_admin
def delete_ai_mapping(workflow_id, mapping_id):
    """Deleta um mapeamento de IA"""
    workflow = Workflow.query.filter_by(
        id=workflow_id,
        organization_id=g.organization_id
    ).first_or_404()
    
    mapping = AIGenerationMapping.query.filter_by(
        id=mapping_id,
        workflow_id=workflow.id
    ).first_or_404()
    
    db.session.delete(mapping)
    db.session.commit()
    
    return jsonify({'success': True})

