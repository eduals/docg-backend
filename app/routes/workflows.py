from flask import Blueprint, request, jsonify, g, current_app
from app.database import db
from app.models import Workflow, Template, DataSourceConnection, WorkflowExecution, Organization
from app.models.workflow import TRIGGER_NODE_TYPES
from app.utils.auth import require_auth, require_org, require_admin
from app.utils.hubspot_auth import flexible_hubspot_auth
from app.engine.flow.normalization import normalize_nodes_from_jsonb
from sqlalchemy.exc import IntegrityError
from datetime import datetime
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
            nodes_data = normalize_nodes_from_jsonb(w.nodes or [], w.edges or [])
            trigger_node = next((n for n in nodes_data if n.get('position') == 1), None)
            if trigger_node and trigger_node.get('config'):
                trigger_config = trigger_node.get('config', {})
                if trigger_config.get('source_object_type') == object_type:
                    filtered_workflows.append(w)
        workflows = filtered_workflows

    result = []
    for w in workflows:
        workflow_dict = workflow_to_dict(w)
        # Adicionar contagem de nodes do JSONB
        nodes_data = normalize_nodes_from_jsonb(w.nodes or [], w.edges or [])
        workflow_dict['nodes_count'] = len(nodes_data)
        workflow_dict['nodes_configured'] = len([n for n in nodes_data if n.get('enabled', True)])
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
    
    result = workflow_to_dict(workflow)

    # Incluir nodes/edges do JSONB (sempre incluir, pois é a estrutura principal)
    result['nodes'] = workflow.nodes or []
    result['edges'] = workflow.edges or []

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
        # Contar workflows reais para mensagem de erro
        current_count = Workflow.query.filter_by(organization_id=org.id).count()
        return jsonify({
            'error': f'Limite de workflows atingido ({current_count}/{limit}). Faça upgrade do plano para criar mais workflows.'
        }), 403
    
    # Criar workflow
    workflow = Workflow(
        organization_id=g.organization_id,
        name=data['name'],
        description=data.get('description'),
        nodes=data.get('nodes', []),
        edges=data.get('edges', []),
        visibility=data.get('visibility', 'private'),
        status='draft',
        created_by=data.get('user_id')
    )
    
    db.session.add(workflow)

    # Incrementar contador de workflows
    if org:
        org.increment_workflow_count()

    db.session.commit()

    return jsonify({
        'success': True,
        'workflow': workflow_to_dict(workflow)
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
    allowed_fields = ['name', 'description', 'nodes', 'edges', 'visibility', 'post_actions', 'status']

    for field in allowed_fields:
        if field in data:
            setattr(workflow, field, data[field])

    workflow.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({
        'success': True,
        'workflow': workflow_to_dict(workflow)
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
    WorkflowExecution.query.filter_by(workflow_id=workflow.id).delete()

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
    
    # Normalizar nodes do JSONB
    nodes_data = normalize_nodes_from_jsonb(workflow.nodes or [], workflow.edges or [])

    if not nodes_data:
        return jsonify({'error': 'Workflow não possui nodes'}), 400

    # Validar que existe trigger node (position = 1)
    trigger_node = next((n for n in nodes_data if n.get('position') == 1), None)
    if not trigger_node:
        return jsonify({'error': 'Workflow deve ter um trigger node (position = 1)'}), 400

    # Validar que todos os nodes obrigatórios estão habilitados
    disabled_nodes = [n for n in nodes_data if not n.get('enabled', True)]
    if len(disabled_nodes) == len(nodes_data):
        return jsonify({'error': 'Todos os nodes estão desabilitados'}), 400

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


# ==================== WORKFLOW EXECUTIONS (RUNS) ENDPOINTS ====================

@workflows_bp.route('/<workflow_id>/runs', methods=['GET'])
@flexible_hubspot_auth
@require_auth
@require_org
def list_workflow_runs(workflow_id):
    """
    Lista execuções (runs) de um workflow.
    
    Query params:
    - limit: Número máximo de execuções (default: 50, max: 100)
    - status: Filtrar por status (running, completed, failed)
    - offset: Paginação (default: 0)
    """
    workflow = Workflow.query.filter_by(
        id=workflow_id,
        organization_id=g.organization_id
    ).first_or_404()
    
    # Parâmetros de paginação
    limit = min(int(request.args.get('limit', 50)), 100)
    offset = int(request.args.get('offset', 0))
    status_filter = request.args.get('status')
    
    # Buscar execuções
    query = WorkflowExecution.query.filter_by(workflow_id=workflow.id)
    
    if status_filter:
        # Mapear status da interface para status do backend
        status_mapping = {
            'running': 'running',
            'success': 'completed',
            'error': 'failed',
            'pending': 'running'  # Pending pode ser considerado running
        }
        backend_status = status_mapping.get(status_filter.lower())
        if backend_status:
            query = query.filter_by(status=backend_status)
    
    # Contar total antes de aplicar paginação
    total_count = query.count()
    
    # Aplicar paginação e ordenação
    executions = query.order_by(WorkflowExecution.started_at.desc()).offset(offset).limit(limit).all()
    
    # Normalizar nodes do JSONB para calcular steps
    nodes_data = normalize_nodes_from_jsonb(workflow.nodes or [], workflow.edges or [])
    total_steps = len([n for n in nodes_data if n.get('position', 0) > 1])  # Excluir trigger (position=1)
    
    # Converter para formato esperado pela interface
    runs = []
    for execution in executions:
        # Mapear status do backend para interface
        status_mapping = {
            'completed': 'success',
            'failed': 'error',
            'running': 'running'
        }
        interface_status = status_mapping.get(execution.status, 'pending')
        
        # Calcular steps_completed baseado em current_node_id ou logs
        steps_completed = None
        if execution.status == 'completed':
            steps_completed = total_steps
        elif execution.status == 'failed':
            # Para failed, contar nodes que foram executados antes do erro
            if execution.execution_logs:
                completed_nodes = [log for log in execution.execution_logs 
                                 if log.get('status') in ['success', 'failed']]
                steps_completed = len(completed_nodes)
            else:
                steps_completed = 0
        elif execution.status == 'running':
            # Para running, calcular baseado no current_node_id ou logs
            if execution.current_node_id:
                # Encontrar posição do node atual
                current_node = next((n for n in nodes_data if n.get('id') == str(execution.current_node_id)), None)
                if current_node:
                    # Contar nodes executados antes do atual (excluindo trigger)
                    steps_completed = len([n for n in nodes_data 
                                         if n.get('position', 0) < current_node.get('position', 0) and n.get('position', 0) > 1])
            elif execution.execution_logs:
                # Calcular baseado nos logs (nodes com status 'success' ou 'failed')
                completed_nodes = [log for log in execution.execution_logs 
                                 if log.get('status') in ['success', 'failed']]
                steps_completed = len(completed_nodes)
        
        # Mapear trigger_type para trigger_source
        trigger_source = execution.trigger_type or 'manual'
        if trigger_source == 'manual':
            trigger_source = 'manual'
        elif trigger_source == 'webhook':
            trigger_source = 'webhook'
        elif trigger_source == 'scheduled':
            trigger_source = 'scheduled'
        
        run_dict = {
            'id': str(execution.id),
            'status': interface_status,
            'started_at': execution.started_at.isoformat() if execution.started_at else None,
            'completed_at': execution.completed_at.isoformat() if execution.completed_at else None,
            'duration_ms': execution.execution_time_ms,
            'trigger_source': trigger_source,
            'trigger_data': execution.trigger_data,
            'error_message': execution.error_message,
            'steps_completed': steps_completed,
            'steps_total': total_steps if total_steps > 0 else None
        }
        
        runs.append(run_dict)
    
    return jsonify({
        'runs': runs,
        'pagination': {
            'total': total_count,
            'limit': limit,
            'offset': offset,
            'has_more': (offset + limit) < total_count
        }
    })


@workflows_bp.route('/<workflow_id>/runs/<run_id>', methods=['GET'])
@flexible_hubspot_auth
@require_auth
@require_org
def get_workflow_run(workflow_id, run_id):
    """
    Retorna detalhes de uma execução específica.
    
    Query params:
    - include_logs: Incluir execution_logs na resposta (default: false)
    """
    workflow = Workflow.query.filter_by(
        id=workflow_id,
        organization_id=g.organization_id
    ).first_or_404()
    
    execution = WorkflowExecution.query.filter_by(
        id=run_id,
        workflow_id=workflow.id
    ).first_or_404()
    
    # Normalizar nodes do JSONB para calcular steps
    nodes_data = normalize_nodes_from_jsonb(workflow.nodes or [], workflow.edges or [])
    total_steps = len([n for n in nodes_data if n.get('position', 0) > 1])
    
    # Mapear status
    status_mapping = {
        'completed': 'success',
        'failed': 'error',
        'running': 'running'
    }
    interface_status = status_mapping.get(execution.status, 'pending')
    
    # Calcular steps_completed baseado em current_node_id ou logs
    steps_completed = None
    if execution.status == 'completed':
        steps_completed = total_steps
    elif execution.status == 'failed':
        # Para failed, contar nodes que foram executados antes do erro
        if execution.execution_logs:
            completed_nodes = [log for log in execution.execution_logs 
                             if log.get('status') in ['success', 'failed']]
            steps_completed = len(completed_nodes)
        else:
            steps_completed = 0
    elif execution.status == 'running':
        # Para running, calcular baseado no current_node_id ou logs
        if execution.current_node_id:
            # Encontrar posição do node atual
            current_node = next((n for n in nodes if str(n.id) == str(execution.current_node_id)), None)
            if current_node:
                # Contar nodes executados antes do atual (excluindo trigger)
                steps_completed = len([n for n in nodes 
                                     if n.position < current_node.position and not n.is_trigger()])
        elif execution.execution_logs:
            # Calcular baseado nos logs (nodes com status 'success' ou 'failed')
            completed_nodes = [log for log in execution.execution_logs 
                             if log.get('status') in ['success', 'failed']]
            steps_completed = len(completed_nodes)
    
    # Buscar informações do node atual
    current_node_info = None
    if execution.current_node_id:
        current_node = next((n for n in nodes_data if n.get('id') == str(execution.current_node_id)), None)
        if current_node:
            current_node_info = {
                'id': current_node.get('id'),
                'node_type': current_node.get('node_type'),
                'position': current_node.get('position'),
                'name': current_node.get('config', {}).get('name')
            }
    
    # Verificar se deve incluir logs
    include_logs = request.args.get('include_logs', 'false').lower() == 'true'
    
    # Mapear trigger_source
    trigger_source = execution.trigger_type or 'manual'
    
    run_dict = {
        'id': str(execution.id),
        'workflow_id': str(execution.workflow_id),
        'status': interface_status,
        'started_at': execution.started_at.isoformat() if execution.started_at else None,
        'completed_at': execution.completed_at.isoformat() if execution.completed_at else None,
        'duration_ms': execution.execution_time_ms,
        'trigger_source': trigger_source,
        'trigger_data': execution.trigger_data,
        'error_message': execution.error_message,
        'steps_completed': steps_completed,
        'steps_total': total_steps if total_steps > 0 else None,
        'generated_document_id': str(execution.generated_document_id) if execution.generated_document_id else None,
        'ai_metrics': execution.ai_metrics,
        'current_node_id': str(execution.current_node_id) if execution.current_node_id else None,
        'current_node': current_node_info,
        'temporal_workflow_id': execution.temporal_workflow_id,
        'temporal_run_id': execution.temporal_run_id
    }
    
    # Incluir logs se solicitado
    if include_logs:
        run_dict['execution_logs'] = execution.execution_logs or []

    return jsonify(run_dict)


# ==================== TAGS PREVIEW ENDPOINTS ====================

@workflows_bp.route('/<workflow_id>/tags/preview', methods=['POST'])
@flexible_hubspot_auth
@require_auth
@require_org
def preview_workflow_tags(workflow_id):
    """
    Preview de resolução de tags antes de gerar documento.

    POST /api/v1/workflows/{workflow_id}/tags/preview

    Body:
    {
        "object_type": "deal",
        "object_id": "123456",
        "template_content": "...",  # Opcional
        "template_id": "uuid"       # Opcional
    }

    Response:
    {
        "tags": [...],
        "loops": [...],
        "conditionals": [...],
        "warnings": [...],
        "errors": [...],
        "sample_output": "...",
        "stats": {...}
    }
    """
    from app.controllers.api.v1.workflows.tags_preview import preview_tags
    return preview_tags(workflow_id)


@workflows_bp.route('/<workflow_id>/tags/validate', methods=['POST'])
@flexible_hubspot_auth
@require_auth
@require_org
def validate_workflow_tags(workflow_id):
    """
    Valida sintaxe de tags sem resolver.

    POST /api/v1/workflows/{workflow_id}/tags/validate

    Body:
    {
        "template_content": "..."
    }

    Response:
    {
        "valid": true,
        "errors": [],
        "tags": ["{{trigger.deal.name}}", ...],
        "tag_count": 5
    }
    """
    from app.controllers.api.v1.workflows.tags_preview import validate_template_tags
    return validate_template_tags(workflow_id)

