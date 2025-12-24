"""
Rotas auxiliares de IA.

Fornece endpoints para listar provedores e modelos disponíveis.
"""

from flask import Blueprint, jsonify, request, g
from app.database import db
from app.models import Workflow, DataSourceConnection
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

    if not workflows:
        return jsonify({
            'ai_tags': [],
            'total': 0,
            'pages': 0,
            'current_page': page
        })

    # Extrair AI mappings do JSONB de todos os workflows
    all_ai_mappings = []
    for workflow in workflows:
        nodes = workflow.nodes or []
        for node in nodes:
            node_data = node.get('data', {})
            node_config = node_data.get('config', {})
            ai_mappings = node_config.get('ai_mappings', [])

            # Adicionar cada AI mapping com metadados
            for mapping in ai_mappings:
                # Aplicar filtros
                if provider and mapping.get('provider', '').lower() != provider.lower():
                    continue

                if search and search.lower() not in mapping.get('ai_tag', '').lower():
                    continue

                all_ai_mappings.append({
                    'ai_tag': mapping.get('ai_tag'),
                    'provider': mapping.get('provider'),
                    'model': mapping.get('model'),
                    'prompt_template': mapping.get('prompt_template'),
                    'temperature': mapping.get('temperature', 0.7),
                    'max_tokens': mapping.get('max_tokens', 1000),
                    'source_fields': mapping.get('source_fields', []),
                    'ai_connection_id': mapping.get('ai_connection_id'),
                    'fallback_value': mapping.get('fallback_value'),
                    'workflow': {
                        'id': str(workflow.id),
                        'name': workflow.name
                    },
                    'node_id': node.get('id'),
                    'node_type': node_data.get('type')
                })

    # Ordenar por provider, model, ai_tag (simulando order by created_at)
    all_ai_mappings.sort(key=lambda x: (x.get('provider', ''), x.get('model', ''), x.get('ai_tag', '')))

    # Paginar manualmente
    total = len(all_ai_mappings)
    start = (page - 1) * per_page
    end = start + per_page
    paginated_mappings = all_ai_mappings[start:end]

    # Adicionar informações de conexão AI
    for mapping in paginated_mappings:
        if mapping.get('ai_connection_id'):
            connection = DataSourceConnection.query.get(mapping['ai_connection_id'])
            if connection:
                mapping['ai_connection'] = {
                    'id': str(connection.id),
                    'name': connection.name or f'{connection.source_type} Connection'
                }
            else:
                mapping['ai_connection'] = None
        else:
            mapping['ai_connection'] = None

    pages = (total + per_page - 1) // per_page if total > 0 else 0

    return jsonify({
        'ai_tags': paginated_mappings,
        'total': total,
        'pages': pages,
        'current_page': page
    })

