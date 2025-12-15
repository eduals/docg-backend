"""
Rotas auxiliares de IA.

Fornece endpoints para listar provedores e modelos disponíveis.
"""

from flask import Blueprint, jsonify, request, g
from app.database import db
from app.models import AIGenerationMapping, Workflow, DataSourceConnection
from app.utils.auth import require_auth, require_org
from app.services.ai.utils import (
    get_available_providers,
    get_available_models,
    SUPPORTED_PROVIDERS,
    PROVIDER_MODELS,
    PROVIDER_NAMES
)
from app.utils.hubspot_auth import flexible_hubspot_auth
import uuid

ai_bp = Blueprint('ai', __name__, url_prefix='/api/v1/ai')


@ai_bp.route('/providers', methods=['GET'])
@flexible_hubspot_auth
def list_providers():
    """
    Lista provedores de IA disponíveis com seus modelos.
    
    Response:
    [
        {
            "id": "openai",
            "name": "OpenAI",
            "models": ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo", ...]
        },
        {
            "id": "gemini",
            "name": "Google Gemini",
            "models": ["gemini-1.5-pro", "gemini-1.5-flash", ...]
        },
        {
            "id": "anthropic",
            "name": "Anthropic",
            "models": ["claude-3-opus", "claude-3-sonnet", "claude-3-haiku", ...]
        }
    ]
    """
    providers = get_available_providers()
    return jsonify(providers)


@ai_bp.route('/providers/<provider>/models', methods=['GET'])
@flexible_hubspot_auth
def list_provider_models(provider):
    """
    Lista modelos disponíveis de um provedor específico.
    
    Response:
    ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo", ...]
    """
    provider = provider.lower()
    
    if provider not in SUPPORTED_PROVIDERS:
        return jsonify({
            'error': f'Provedor não suportado. Use: {", ".join(SUPPORTED_PROVIDERS)}'
        }), 400
    
    models = get_available_models(provider)
    return jsonify(models)


@ai_bp.route('/providers/<provider>', methods=['GET'])
@flexible_hubspot_auth
def get_provider_info(provider):
    """
    Retorna informações detalhadas de um provedor.
    
    Response:
    {
        "id": "openai",
        "name": "OpenAI",
        "models": ["gpt-4", ...],
        "description": "...",
        "docs_url": "..."
    }
    """
    provider = provider.lower()
    
    if provider not in SUPPORTED_PROVIDERS:
        return jsonify({
            'error': f'Provedor não suportado. Use: {", ".join(SUPPORTED_PROVIDERS)}'
        }), 400
    
    # Informações adicionais por provedor
    provider_info = {
        'openai': {
            'description': 'OpenAI oferece modelos GPT avançados para geração de texto.',
            'docs_url': 'https://platform.openai.com/docs',
            'recommended_model': 'gpt-4o'
        },
        'gemini': {
            'description': 'Google Gemini oferece modelos multimodais de alta performance.',
            'docs_url': 'https://ai.google.dev/docs',
            'recommended_model': 'gemini-1.5-pro'
        },
        'anthropic': {
            'description': 'Anthropic oferece modelos Claude focados em segurança e confiabilidade.',
            'docs_url': 'https://docs.anthropic.com',
            'recommended_model': 'claude-3-5-sonnet-20241022'
        }
    }
    
    info = provider_info.get(provider, {})
    
    return jsonify({
        'id': provider,
        'name': PROVIDER_NAMES.get(provider, provider.title()),
        'models': PROVIDER_MODELS.get(provider, []),
        'description': info.get('description', ''),
        'docs_url': info.get('docs_url', ''),
        'recommended_model': info.get('recommended_model', '')
    })


@ai_bp.route('/tags', methods=['GET'])
@flexible_hubspot_auth
@require_auth
@require_org
def list_ai_tags():
    """
    Lista todas as tags AI da organização com paginação e filtros.
    
    Query params:
    - page: número da página (default: 1)
    - per_page: itens por página (default: 20)
    - workflow_id: filtrar por workflow específico
    - provider: filtrar por provedor (openai, gemini, anthropic)
    - search: busca parcial por ai_tag
    
    Response:
    {
        "ai_tags": [...],
        "total": 50,
        "pages": 3,
        "current_page": 1
    }
    """
    org_id = uuid.UUID(g.organization_id) if isinstance(g.organization_id, str) else g.organization_id
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    workflow_id = request.args.get('workflow_id')
    provider = request.args.get('provider')
    search = request.args.get('search')
    
    # Buscar workflows da organização
    workflows_query = Workflow.query.filter_by(organization_id=org_id)
    if workflow_id:
        workflows_query = workflows_query.filter_by(id=workflow_id)
    
    workflows = workflows_query.all()
    workflow_ids = [w.id for w in workflows]
    
    if not workflow_ids:
        return jsonify({
            'ai_tags': [],
            'total': 0,
            'pages': 0,
            'current_page': page
        })
    
    # Construir query base para AI mappings
    query = AIGenerationMapping.query.filter(
        AIGenerationMapping.workflow_id.in_(workflow_ids)
    )
    
    # Aplicar filtros
    if provider:
        query = query.filter_by(provider=provider.lower())
    
    if search:
        query = query.filter(AIGenerationMapping.ai_tag.ilike(f'%{search}%'))
    
    # Ordenar por data de criação (mais recente primeiro)
    query = query.order_by(AIGenerationMapping.created_at.desc())
    
    # Paginar
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    # Construir resposta com dados relacionados
    ai_tags = []
    for mapping in pagination.items:
        tag_dict = mapping.to_dict()
        
        # Buscar workflow relacionado
        workflow = Workflow.query.get(mapping.workflow_id)
        if workflow:
            tag_dict['workflow'] = {
                'id': str(workflow.id),
                'name': workflow.name
            }
        else:
            tag_dict['workflow'] = None
        
        # Buscar conexão AI relacionada
        if mapping.ai_connection_id:
            connection = DataSourceConnection.query.get(mapping.ai_connection_id)
            if connection:
                tag_dict['ai_connection'] = {
                    'id': str(connection.id),
                    'name': connection.name or f'{connection.source_type} Connection'
                }
            else:
                tag_dict['ai_connection'] = None
        else:
            tag_dict['ai_connection'] = None
        
        ai_tags.append(tag_dict)
    
    return jsonify({
        'ai_tags': ai_tags,
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': page
    })

