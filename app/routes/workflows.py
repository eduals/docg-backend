from flask import Blueprint, request, jsonify, g, current_app
from app.database import db
from app.models import Workflow, WorkflowFieldMapping, Template, AIGenerationMapping, DataSourceConnection, WorkflowNode, WorkflowExecution, Organization
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
    import uuid
    org_id = g.organization_id
    status = request.args.get('status')
    object_type = request.args.get('object_type')  # Para filtrar por tipo de objeto
    
    query = Workflow.query.filter_by(organization_id=org_id)
    
    if status:
        query = query.filter_by(status=status)
    
    workflows = query.order_by(Workflow.updated_at.desc()).all()
    
    # Se object_type foi fornecido, filtrar workflows que têm trigger node configurado para esse tipo
    if object_type:
        filtered_workflows = []
        for w in workflows:
            trigger_node = WorkflowNode.query.filter_by(
                workflow_id=w.id,
                node_type='trigger'
            ).first()
            if trigger_node and trigger_node.config:
                trigger_config = trigger_node.config or {}
                if trigger_config.get('source_object_type') == object_type:
                    filtered_workflows.append(w)
        workflows = filtered_workflows
    
    result = []
    for w in workflows:
        workflow_dict = workflow_to_dict(w)
        # Adicionar contagem de nodes
        nodes_count = WorkflowNode.query.filter_by(workflow_id=w.id).count()
        nodes_configured = WorkflowNode.query.filter_by(
            workflow_id=w.id,
            status='configured'
        ).count()
        workflow_dict['nodes_count'] = nodes_count
        workflow_dict['nodes_configured'] = nodes_configured
        result.append(workflow_dict)
    
    return jsonify({
        'workflows': result
    })


@workflows_bp.route('/<workflow_id>', methods=['GET'])
@flexible_hubspot_auth
@require_auth
@require_org
def get_workflow(workflow_id):
    """Retorna detalhes de um workflow"""
    import uuid
    workflow = Workflow.query.filter_by(
        id=workflow_id,
        organization_id=g.organization_id
    ).first_or_404()
    
    include_nodes = request.args.get('include_nodes', 'false').lower() == 'true'
    include_mappings = request.args.get('include_mappings', 'false').lower() == 'true'
    include_ai_mappings = request.args.get('include_ai_mappings', 'false').lower() == 'true'
    
    result = workflow_to_dict(workflow, include_mappings=include_mappings, include_ai_mappings=include_ai_mappings)
    
    if include_nodes:
        nodes = WorkflowNode.query.filter_by(
            workflow_id=workflow.id
        ).order_by(WorkflowNode.position).all()
        result['nodes'] = [node.to_dict(include_config=True) for node in nodes]
    
    return jsonify(result)


@workflows_bp.route('', methods=['POST'])
@flexible_hubspot_auth
@require_auth
@require_org
@require_admin
def create_workflow():
    """
    Cria um novo workflow com trigger node automaticamente.
    
    Body:
    {
        "name": "Quote Generator",
        "description": "...",
        "source_connection_id": "uuid",  // Para trigger node
        "source_object_type": "deal",     // Para trigger node
        "trigger_type": "manual",        // Para trigger node
        "trigger_config": {},            // Para trigger node
        "post_actions": {}               // Opcional
    }
    """
    import uuid
    data = request.get_json()
    
    # Validações
    if not data.get('name'):
        return jsonify({'error': 'name é obrigatório'}), 400
    
    # Validar post_actions se fornecido
    post_actions = data.get('post_actions')
    if post_actions:
        is_valid, error_msg = validate_post_actions(post_actions)
        if not is_valid:
            return jsonify({'error': error_msg}), 400
    
    # Verificar limite de workflows
    org = Organization.query.filter_by(id=g.organization_id).first()
    if org and not org.can_create_workflow():
        limit = org.workflows_limit
        used = org.workflows_used
        return jsonify({
            'error': f'Limite de workflows atingido ({used}/{limit}). Faça upgrade do plano para criar mais workflows.'
        }), 403
    
    # Criar workflow (estrutura simplificada)
    workflow = Workflow(
        organization_id=g.organization_id,
        name=data['name'],
        description=data.get('description'),
        post_actions=data.get('post_actions'),
        status='draft',
        created_by=data.get('user_id')
    )
    
    db.session.add(workflow)
    db.session.flush()  # Para obter o ID
    
    # Criar trigger node automaticamente
    trigger_type = data.get('trigger_type', 'manual')
    trigger_config = {
        'trigger_type': trigger_type,
        'source_connection_id': str(data.get('source_connection_id')) if data.get('source_connection_id') else None,
        'source_object_type': data.get('source_object_type'),
        'trigger_config': data.get('trigger_config', {}),
        'field_mapping': data.get('field_mapping', {})  # Para webhook trigger
    }
    
    trigger_node = WorkflowNode(
        workflow_id=workflow.id,
        node_type='trigger',
        position=1,
        parent_node_id=None,
        config=trigger_config,
        status='draft'
    )
    
    # Se for webhook trigger, gerar token
    if trigger_type == 'webhook':
        trigger_node.generate_webhook_token()
    
    db.session.add(trigger_node)
    
    # Incrementar contador de workflows
    if org:
        org.increment_workflow_count()
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'workflow': workflow_to_dict(workflow, include_mappings=False),
        'trigger_node': trigger_node.to_dict(include_config=True)
    }), 201


@workflows_bp.route('/<workflow_id>', methods=['PUT'])
@flexible_hubspot_auth
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
@flexible_hubspot_auth
@require_auth
@require_org
@require_admin
def delete_workflow(workflow_id):
    """Deleta um workflow"""
    workflow = Workflow.query.filter_by(
        id=workflow_id,
        organization_id=g.organization_id
    ).first_or_404()
    
    # Deletar execuções explicitamente antes de deletar o workflow
    # Isso evita que o SQLAlchemy tente fazer UPDATE com workflow_id=NULL
    WorkflowExecution.query.filter_by(workflow_id=workflow.id).delete()
    
    # Deletar field mappings explicitamente
    WorkflowFieldMapping.query.filter_by(workflow_id=workflow.id).delete()
    
    # Deletar AI mappings explicitamente
    AIGenerationMapping.query.filter_by(workflow_id=workflow.id).delete()
    
    # Deletar nodes explicitamente antes de deletar o workflow
    # Isso evita que o SQLAlchemy tente fazer UPDATE com workflow_id=NULL
    WorkflowNode.query.filter_by(workflow_id=workflow.id).delete()
    
    # Deletar o workflow
    db.session.delete(workflow)
    db.session.commit()
    
    logger.info(f'Workflow {workflow_id} deletado com sucesso')
    
    return jsonify({'success': True})


@workflows_bp.route('/<workflow_id>/activate', methods=['POST'])
@flexible_hubspot_auth
@require_auth
@require_org
@require_admin
def activate_workflow(workflow_id):
    """Ativa um workflow (valida nodes antes)"""
    workflow = Workflow.query.filter_by(
        id=workflow_id,
        organization_id=g.organization_id
    ).first_or_404()
    
    # Buscar nodes
    nodes = WorkflowNode.query.filter_by(
        workflow_id=workflow.id
    ).order_by(WorkflowNode.position).all()
    
    # Validar que existe trigger node
    trigger_node = next((n for n in nodes if n.is_trigger()), None)
    if not trigger_node:
        return jsonify({'error': 'Workflow deve ter um trigger node'}), 400
    
    # Validar que trigger está configurado
    if not trigger_node.is_configured():
        return jsonify({'error': 'Trigger node não está configurado'}), 400
    
    # Validar que todos os nodes obrigatórios estão configurados
    unconfigured_nodes = [n for n in nodes if not n.is_configured() and n.node_type != 'trigger']
    if unconfigured_nodes:
        return jsonify({
            'error': f'{len(unconfigured_nodes)} node(s) não estão configurados',
            'unconfigured_nodes': [str(n.id) for n in unconfigured_nodes]
        }), 400
    
    # Validar cadeia de nodes (sem gaps)
    positions = sorted([n.position for n in nodes])
    expected_positions = list(range(1, len(nodes) + 1))
    if positions != expected_positions:
        return jsonify({
            'error': 'Cadeia de nodes incompleta. Existem gaps nas posições.'
        }), 400
    
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
        'post_actions': workflow.post_actions,
        'created_at': workflow.created_at.isoformat() if workflow.created_at else None,
        'updated_at': workflow.updated_at.isoformat() if workflow.updated_at else None
    }
    
    # Manter campos legados para compatibilidade durante transição (deprecated)
    # Estes campos agora vêm dos nodes
    result['source_connection_id'] = str(workflow.source_connection_id) if workflow.source_connection_id else None
    result['source_object_type'] = workflow.source_object_type
    result['template_id'] = str(workflow.template_id) if workflow.template_id else None
    result['output_folder_id'] = workflow.output_folder_id
    result['output_name_template'] = workflow.output_name_template
    result['create_pdf'] = workflow.create_pdf
    result['trigger_type'] = workflow.trigger_type
    result['trigger_config'] = workflow.trigger_config
    
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
    
    # Incluir info do template se disponível (legado)
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
@flexible_hubspot_auth
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
@flexible_hubspot_auth
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
@flexible_hubspot_auth
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
@flexible_hubspot_auth
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
@flexible_hubspot_auth
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


# ==================== WORKFLOW NODES ENDPOINTS ====================

@workflows_bp.route('/<workflow_id>/nodes', methods=['GET'])
@flexible_hubspot_auth
@require_auth
@require_org
def list_workflow_nodes(workflow_id):
    """Lista nodes de um workflow ordenados por position"""
    workflow = Workflow.query.filter_by(
        id=workflow_id,
        organization_id=g.organization_id
    ).first_or_404()
    
    nodes = WorkflowNode.query.filter_by(
        workflow_id=workflow.id
    ).order_by(WorkflowNode.position).all()
    
    return jsonify({
        'nodes': [node.to_dict(include_config=True) for node in nodes]
    })


@workflows_bp.route('/<workflow_id>/nodes/<node_id>', methods=['GET'])
@flexible_hubspot_auth
@require_auth
@require_org
def get_workflow_node(workflow_id, node_id):
    """Retorna detalhes de um node"""
    workflow = Workflow.query.filter_by(
        id=workflow_id,
        organization_id=g.organization_id
    ).first_or_404()
    
    node = WorkflowNode.query.filter_by(
        id=node_id,
        workflow_id=workflow.id
    ).first_or_404()
    
    return jsonify(node.to_dict(include_config=True))


@workflows_bp.route('/<workflow_id>/nodes', methods=['POST'])
@flexible_hubspot_auth
@require_auth
@require_org
@require_admin
def create_workflow_node(workflow_id):
    """
    Cria um novo node no workflow.
    
    Body:
    {
        "node_type": "google-docs",
        "position": 2,
        "parent_node_id": "uuid",
        "config": {}
    }
    """
    workflow = Workflow.query.filter_by(
        id=workflow_id,
        organization_id=g.organization_id
    ).first_or_404()
    
    data = request.get_json()
    
    # Validações
    if not data.get('node_type'):
        return jsonify({'error': 'node_type é obrigatório'}), 400
    
    node_type = data['node_type']
    valid_types = ['trigger', 'google-docs', 'google-slides', 'microsoft-word', 'microsoft-powerpoint', 'gmail', 'outlook', 'clicksign', 'webhook', 'human-in-loop']
    if node_type not in valid_types:
        return jsonify({
            'error': f'node_type deve ser um de: {", ".join(valid_types)}'
        }), 400
    
    # Se for trigger, verificar se já existe
    if node_type == 'trigger':
        existing_trigger = WorkflowNode.query.filter_by(
            workflow_id=workflow.id,
            node_type='trigger'
        ).first()
        if existing_trigger:
            return jsonify({
                'error': 'Workflow já possui um trigger node. Cada workflow pode ter apenas um trigger.'
            }), 400
    
    # Determinar position se não fornecido
    position = data.get('position')
    if not position:
        # Buscar último position
        last_node = WorkflowNode.query.filter_by(
            workflow_id=workflow.id
        ).order_by(WorkflowNode.position.desc()).first()
        position = (last_node.position + 1) if last_node else 1
    
    # Se position for 1 e não for trigger, retornar erro
    if position == 1 and node_type != 'trigger':
        return jsonify({
            'error': 'O primeiro node (position=1) deve ser do tipo trigger'
        }), 400
    
    # Validar parent_node_id se fornecido
    parent_node_id = data.get('parent_node_id')
    if parent_node_id:
        parent = WorkflowNode.query.filter_by(
            id=parent_node_id,
            workflow_id=workflow.id
        ).first()
        if not parent:
            return jsonify({'error': 'parent_node_id não encontrado'}), 400
    
    # Criar node
    node = WorkflowNode(
        workflow_id=workflow.id,
        node_type=node_type,
        position=position,
        parent_node_id=parent_node_id,
        config=data.get('config', {}),
        status='draft'
    )
    
    db.session.add(node)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'node': node.to_dict(include_config=True)
    }), 201


@workflows_bp.route('/<workflow_id>/nodes/<node_id>', methods=['PUT'])
@flexible_hubspot_auth
@require_auth
@require_org
@require_admin
def update_workflow_node(workflow_id, node_id):
    """Atualiza um node do workflow"""
    workflow = Workflow.query.filter_by(
        id=workflow_id,
        organization_id=g.organization_id
    ).first_or_404()
    
    node = WorkflowNode.query.filter_by(
        id=node_id,
        workflow_id=workflow.id
    ).first_or_404()
    
    data = request.get_json()
    
    # Não permitir alterar node_type do trigger
    if node.is_trigger() and 'node_type' in data and data['node_type'] != 'trigger':
        return jsonify({
            'error': 'Não é possível alterar o tipo do trigger node'
        }), 400
    
    # Atualizar campos permitidos
    if 'position' in data:
        # Validar que não está tentando colocar outro node na position 1
        if data['position'] == 1 and not node.is_trigger():
            return jsonify({
                'error': 'Apenas o trigger node pode ter position=1'
            }), 400
        node.position = data['position']
    
    if 'parent_node_id' in data:
        parent_node_id = data['parent_node_id']
        if parent_node_id:
            parent = WorkflowNode.query.filter_by(
                id=parent_node_id,
                workflow_id=workflow.id
            ).first()
            if not parent:
                return jsonify({'error': 'parent_node_id não encontrado'}), 400
        node.parent_node_id = parent_node_id
    
    if 'config' in data:
        node.config = data['config']
        # Atualizar status baseado na configuração
        if node.is_configured():
            node.status = 'configured'
        else:
            node.status = 'draft'
    
    if 'status' in data:
        node.status = data['status']
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'node': node.to_dict(include_config=True)
    })


@workflows_bp.route('/<workflow_id>/nodes/<node_id>', methods=['DELETE'])
@flexible_hubspot_auth
@require_auth
@require_org
@require_admin
def delete_workflow_node(workflow_id, node_id):
    """Deleta um node do workflow"""
    workflow = Workflow.query.filter_by(
        id=workflow_id,
        organization_id=g.organization_id
    ).first_or_404()
    
    node = WorkflowNode.query.filter_by(
        id=node_id,
        workflow_id=workflow.id
    ).first_or_404()
    
    # Não permitir deletar trigger node
    if node.is_trigger():
        return jsonify({
            'error': 'Não é possível deletar o trigger node'
        }), 400
    
    # Verificar se há nodes filhos
    children = WorkflowNode.query.filter_by(
        parent_node_id=node.id
    ).count()
    
    if children > 0:
        return jsonify({
            'error': f'Não é possível deletar node com {children} node(s) filho(s). Remova os nodes filhos primeiro.'
        }), 400
    
    db.session.delete(node)
    db.session.commit()
    
    return jsonify({'success': True})


@workflows_bp.route('/<workflow_id>/nodes/order', methods=['PUT'])
@flexible_hubspot_auth
@require_auth
@require_org
@require_admin
def reorder_workflow_nodes(workflow_id):
    """
    Reordena nodes do workflow.
    
    Body:
    {
        "node_order": [
            {"node_id": "uuid1", "position": 1},
            {"node_id": "uuid2", "position": 2}
        ]
    }
    """
    workflow = Workflow.query.filter_by(
        id=workflow_id,
        organization_id=g.organization_id
    ).first_or_404()
    
    data = request.get_json()
    node_order = data.get('node_order', [])
    
    if not node_order:
        return jsonify({'error': 'node_order é obrigatório'}), 400
    
    # Validar que todos os nodes pertencem ao workflow
    node_ids = [item['node_id'] for item in node_order]
    nodes = WorkflowNode.query.filter(
        WorkflowNode.id.in_(node_ids),
        WorkflowNode.workflow_id == workflow.id
    ).all()
    
    if len(nodes) != len(node_ids):
        return jsonify({
            'error': 'Um ou mais nodes não pertencem a este workflow'
        }), 400
    
    # Validar que position 1 é um trigger
    position_1_node = next((item for item in node_order if item['position'] == 1), None)
    if position_1_node:
        node_1 = next((n for n in nodes if str(n.id) == position_1_node['node_id']), None)
        if not node_1 or not node_1.is_trigger():
            return jsonify({
                'error': 'O node na position 1 deve ser do tipo trigger'
            }), 400
    
    # Atualizar positions em duas etapas para evitar conflito de constraint única
    try:
        # Etapa 1: Atualizar todos para posições temporárias (negativas)
        # Isso evita conflito quando dois nodes precisam trocar de posição
        for idx, item in enumerate(node_order):
            node = next((n for n in nodes if str(n.id) == item['node_id']), None)
            if node:
                temp_position = -(idx + 1000)  # Posições temporárias negativas (ex: -1000, -1001, etc.)
                node.position = temp_position
        
        db.session.commit()  # Commit das posições temporárias
        
        # Etapa 2: Atualizar para posições finais
        for item in node_order:
            node = next((n for n in nodes if str(n.id) == item['node_id']), None)
            if node:
                node.position = item['position']
        
        db.session.commit()
        
        current_app.logger.info(f'Nodes reordenados com sucesso no workflow {workflow_id}')
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Erro ao reordenar nodes no workflow {workflow_id}: {str(e)}')
        return jsonify({'error': f'Erro ao reordenar nodes: {str(e)}'}), 500


@workflows_bp.route('/<workflow_id>/nodes/<node_id>/config', methods=['GET'])
@flexible_hubspot_auth
@require_auth
@require_org
def get_workflow_node_config(workflow_id, node_id):
    """Retorna configuração de um node"""
    workflow = Workflow.query.filter_by(
        id=workflow_id,
        organization_id=g.organization_id
    ).first_or_404()
    
    node = WorkflowNode.query.filter_by(
        id=node_id,
        workflow_id=workflow.id
    ).first_or_404()
    
    response_data = {
        'config': node.config or {},
        'status': node.status
    }
    
    # Adicionar webhook_token se for trigger node
    if node.node_type == 'trigger' and node.webhook_token:
        response_data['webhook_token'] = node.webhook_token
    
    return jsonify(response_data)


@workflows_bp.route('/<workflow_id>/nodes/<node_id>/config', methods=['PUT'])
@flexible_hubspot_auth
@require_auth
@require_org
@require_admin
def update_workflow_node_config(workflow_id, node_id):
    """
    Atualiza configuração de um node.
    
    Body:
    {
        "config": {
            "template_id": "uuid",
            "output_name_template": "...",
            ...
        }
    }
    """
    workflow = Workflow.query.filter_by(
        id=workflow_id,
        organization_id=g.organization_id
    ).first_or_404()
    
    node = WorkflowNode.query.filter_by(
        id=node_id,
        workflow_id=workflow.id
    ).first_or_404()
    
    data = request.get_json()
    
    if 'config' not in data:
        return jsonify({'error': 'config é obrigatório'}), 400
    
    node.config = data['config']
    
    # Atualizar status baseado na configuração
    if node.is_configured():
        node.status = 'configured'
    else:
        node.status = 'draft'
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'config': node.config,
        'status': node.status
    })


@workflows_bp.route('/<workflow_id>/field-mappings', methods=['GET'])
@flexible_hubspot_auth
@require_auth
@require_org
def get_workflow_field_mappings(workflow_id):
    """
    Retorna field mappings de todos os nodes Google Docs do workflow.
    Útil para mostrar no HubSpot App quais tags serão preenchidas.
    """
    workflow = Workflow.query.filter_by(
        id=workflow_id,
        organization_id=g.organization_id
    ).first_or_404()
    
    # Buscar nodes Google Docs
    google_docs_nodes = WorkflowNode.query.filter_by(
        workflow_id=workflow.id,
        node_type='google-docs'
    ).all()
    
    # Extrair field mappings de cada node
    all_mappings = []
    for node in google_docs_nodes:
        config = node.config or {}
        field_mappings = config.get('field_mappings', [])
        for mapping in field_mappings:
            all_mappings.append({
                'node_id': str(node.id),
                'template_tag': mapping.get('template_tag'),
                'source_field': mapping.get('source_field'),
                'transform_type': mapping.get('transform_type'),
                'default_value': mapping.get('default_value')
            })
    
    # Também incluir field mappings legados do workflow (para compatibilidade)
    legacy_mappings = list(workflow.field_mappings)
    for mapping in legacy_mappings:
        all_mappings.append({
            'node_id': None,  # Indica que é mapping legado
            'template_tag': mapping.template_tag,
            'source_field': mapping.source_field,
            'transform_type': mapping.transform_type,
            'default_value': mapping.default_value
        })
    
    # Buscar AI mappings também
    ai_mappings = []
    for mapping in workflow.ai_mappings:
        ai_mappings.append({
            'ai_tag': mapping.ai_tag,
            'source_fields': mapping.source_fields,
            'provider': mapping.provider,
            'model': mapping.model
        })
    
    return jsonify({
        'field_mappings': all_mappings,
        'ai_mappings': ai_mappings
    })


@workflows_bp.route('/<workflow_id>/preview', methods=['GET'])
@flexible_hubspot_auth
@require_auth
@require_org
def preview_workflow_data(workflow_id):
    """
    Preview dos dados que serão usados ao gerar documento.
    
    Query params:
    - object_type: deal, contact, company, ticket (obrigatório)
    - object_id: ID do objeto no HubSpot (obrigatório)
    """
    workflow = Workflow.query.filter_by(
        id=workflow_id,
        organization_id=g.organization_id
    ).first_or_404()
    
    object_type = request.args.get('object_type')
    object_id = request.args.get('object_id')
    
    if not object_type or not object_id:
        return jsonify({
            'error': 'object_type e object_id são obrigatórios'
        }), 400
    
    try:
        # Buscar trigger node para obter conexão
        trigger_node = WorkflowNode.query.filter_by(
            workflow_id=workflow.id,
            node_type='trigger'
        ).first()
        
        if not trigger_node or not trigger_node.config:
            return jsonify({
                'error': 'Trigger node não configurado'
            }), 400
        
        trigger_config = trigger_node.config
        source_connection_id = trigger_config.get('source_connection_id')
        
        if not source_connection_id:
            return jsonify({
                'error': 'Conexão de dados não configurada no trigger'
            }), 400
        
        # Buscar conexão
        connection = DataSourceConnection.query.get(source_connection_id)
        if not connection:
            return jsonify({
                'error': 'Conexão não encontrada'
            }), 400
        
        # Buscar dados do objeto
        from app.services.data_sources.hubspot import HubSpotDataSource
        data_source = HubSpotDataSource(connection)
        source_data = data_source.get_object_data(object_type, object_id)
        
        # Normalizar dados
        if isinstance(source_data, dict) and 'properties' in source_data:
            properties = source_data.pop('properties', {})
            if isinstance(properties, dict):
                source_data.update(properties)
        
        # Buscar field mappings
        google_docs_nodes = WorkflowNode.query.filter_by(
            workflow_id=workflow.id,
            node_type='google-docs'
        ).all()
        
        field_mappings_preview = []
        for node in google_docs_nodes:
            config = node.config or {}
            field_mappings = config.get('field_mappings', [])
            
            for mapping in field_mappings:
                template_tag = mapping.get('template_tag')
                source_field = mapping.get('source_field')
                
                # Buscar valor
                from app.services.document_generation.tag_processor import TagProcessor
                value = TagProcessor._get_nested_value(source_data, source_field)
                
                field_mappings_preview.append({
                    'template_tag': template_tag,
                    'source_field': source_field,
                    'value': value,
                    'status': 'ok' if value is not None else 'missing',
                    'label': template_tag.replace('_', ' ').title()
                })
        
        # Buscar AI mappings
        ai_mappings_preview = []
        for mapping in workflow.ai_mappings:
            ai_mappings_preview.append({
                'ai_tag': mapping.ai_tag,
                'source_fields': mapping.source_fields,
                'provider': mapping.provider,
                'model': mapping.model,
                'preview': f'[AI: {mapping.ai_tag}]'  # Placeholder
            })
        
        # Validação
        missing_fields = [m['source_field'] for m in field_mappings_preview if m['status'] == 'missing']
        all_tags_available = len(missing_fields) == 0
        
        return jsonify({
            'field_mappings': field_mappings_preview,
            'ai_mappings': ai_mappings_preview,
            'validation': {
                'all_tags_available': all_tags_available,
                'missing_fields': missing_fields,
                'warnings': []
            }
        })
        
    except Exception as e:
        logger.error(f"Erro ao gerar preview: {str(e)}")
        return jsonify({
            'error': str(e)
        }), 500

