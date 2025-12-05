"""
Rotas auxiliares de IA.

Fornece endpoints para listar provedores e modelos disponíveis.
"""

from flask import Blueprint, jsonify
from app.utils.auth import require_auth
from app.services.ai.utils import (
    get_available_providers,
    get_available_models,
    SUPPORTED_PROVIDERS,
    PROVIDER_MODELS,
    PROVIDER_NAMES
)

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

