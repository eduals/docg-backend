"""
Utilitários e helpers para o serviço de IA.
"""

from typing import List, Dict, Optional

# Provedores suportados
SUPPORTED_PROVIDERS = ['openai', 'gemini', 'anthropic']

# Modelos disponíveis por provedor
PROVIDER_MODELS = {
    'openai': [
        'gpt-4',
        'gpt-4-turbo',
        'gpt-4-turbo-preview',
        'gpt-4o',
        'gpt-4o-mini',
        'gpt-3.5-turbo',
        'gpt-3.5-turbo-16k',
    ],
    'gemini': [
        'gemini-1.5-pro',
        'gemini-1.5-flash',
        'gemini-1.0-pro',
        'gemini-pro',
    ],
    'anthropic': [
        'claude-3-opus-20240229',
        'claude-3-sonnet-20240229',
        'claude-3-haiku-20240307',
        'claude-3-5-sonnet-20241022',
    ],
}

# Nomes amigáveis dos provedores
PROVIDER_NAMES = {
    'openai': 'OpenAI',
    'gemini': 'Google Gemini',
    'anthropic': 'Anthropic',
}

# Custos estimados por 1K tokens (input/output em USD)
# Valores aproximados, podem variar
COST_PER_1K_TOKENS = {
    'openai': {
        'gpt-4': {'input': 0.03, 'output': 0.06},
        'gpt-4-turbo': {'input': 0.01, 'output': 0.03},
        'gpt-4o': {'input': 0.005, 'output': 0.015},
        'gpt-4o-mini': {'input': 0.00015, 'output': 0.0006},
        'gpt-3.5-turbo': {'input': 0.0005, 'output': 0.0015},
    },
    'gemini': {
        'gemini-1.5-pro': {'input': 0.00125, 'output': 0.005},
        'gemini-1.5-flash': {'input': 0.000075, 'output': 0.0003},
        'gemini-pro': {'input': 0.00025, 'output': 0.0005},
    },
    'anthropic': {
        'claude-3-opus': {'input': 0.015, 'output': 0.075},
        'claude-3-sonnet': {'input': 0.003, 'output': 0.015},
        'claude-3-haiku': {'input': 0.00025, 'output': 0.00125},
        'claude-3-5-sonnet': {'input': 0.003, 'output': 0.015},
    },
}


def get_model_string(provider: str, model: str) -> str:
    """
    Retorna string de modelo para LiteLLM.
    
    Args:
        provider: Provedor (openai, gemini, anthropic)
        model: Nome do modelo
    
    Returns:
        String no formato 'provider/model' para LiteLLM
    
    Examples:
        >>> get_model_string('openai', 'gpt-4')
        'openai/gpt-4'
        >>> get_model_string('gemini', 'gemini-1.5-pro')
        'gemini/gemini-1.5-pro'
    """
    provider = provider.lower().strip()
    model = model.strip()
    
    # Mapeamento de provedores para prefixo LiteLLM
    provider_prefix = {
        'openai': 'openai',
        'gemini': 'gemini',
        'anthropic': 'anthropic',
    }
    
    prefix = provider_prefix.get(provider, provider)
    return f"{prefix}/{model}"


def get_available_providers() -> List[Dict]:
    """
    Lista provedores disponíveis com seus modelos.
    
    Returns:
        Lista de dicionários com id, name e models
    """
    return [
        {
            'id': provider,
            'name': PROVIDER_NAMES.get(provider, provider.title()),
            'models': PROVIDER_MODELS.get(provider, [])
        }
        for provider in SUPPORTED_PROVIDERS
    ]


def get_available_models(provider: str) -> List[str]:
    """
    Lista modelos disponíveis para um provedor.
    
    Args:
        provider: Nome do provedor
    
    Returns:
        Lista de nomes de modelos disponíveis
    """
    provider = provider.lower().strip()
    return PROVIDER_MODELS.get(provider, [])


def validate_provider(provider: str) -> bool:
    """
    Valida se o provedor é suportado.
    
    Args:
        provider: Nome do provedor
    
    Returns:
        True se válido, False caso contrário
    """
    return provider.lower().strip() in SUPPORTED_PROVIDERS


def validate_model(provider: str, model: str) -> bool:
    """
    Valida se o modelo é suportado para o provedor.
    
    Args:
        provider: Nome do provedor
        model: Nome do modelo
    
    Returns:
        True se válido, False caso contrário
    """
    provider = provider.lower().strip()
    models = PROVIDER_MODELS.get(provider, [])
    
    # Verifica match exato ou parcial (para versões específicas)
    for m in models:
        if m == model or model.startswith(m):
            return True
    
    return False


def estimate_cost(provider: str, model: str, input_tokens: int, output_tokens: int) -> float:
    """
    Estima custo em USD baseado em tokens.
    
    Args:
        provider: Nome do provedor
        model: Nome do modelo
        input_tokens: Número de tokens de entrada
        output_tokens: Número de tokens de saída
    
    Returns:
        Custo estimado em USD
    """
    provider = provider.lower().strip()
    
    provider_costs = COST_PER_1K_TOKENS.get(provider, {})
    
    # Tenta match exato ou parcial
    model_costs = None
    for m, costs in provider_costs.items():
        if m == model or model.startswith(m):
            model_costs = costs
            break
    
    if not model_costs:
        # Valor default conservador
        model_costs = {'input': 0.01, 'output': 0.03}
    
    input_cost = (input_tokens / 1000) * model_costs['input']
    output_cost = (output_tokens / 1000) * model_costs['output']
    
    return round(input_cost + output_cost, 6)


def get_api_key_env_var(provider: str) -> str:
    """
    Retorna o nome da variável de ambiente para API key do provedor.
    
    Args:
        provider: Nome do provedor
    
    Returns:
        Nome da variável de ambiente
    """
    env_vars = {
        'openai': 'OPENAI_API_KEY',
        'gemini': 'GEMINI_API_KEY',
        'anthropic': 'ANTHROPIC_API_KEY',
    }
    return env_vars.get(provider.lower(), f'{provider.upper()}_API_KEY')


def normalize_provider_name(provider: str) -> str:
    """
    Normaliza o nome do provedor.
    
    Args:
        provider: Nome do provedor (pode ter case misto)
    
    Returns:
        Nome normalizado (lowercase)
    """
    aliases = {
        'gpt': 'openai',
        'chatgpt': 'openai',
        'google': 'gemini',
        'claude': 'anthropic',
    }
    
    normalized = provider.lower().strip()
    return aliases.get(normalized, normalized)

