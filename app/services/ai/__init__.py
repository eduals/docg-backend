"""
AI Services - Serviços para geração de texto usando LLMs.

Este módulo fornece integração com múltiplos provedores de IA através do LiteLLM.
"""

from .llm_service import LLMService, LLMResponse
from .exceptions import (
    AIGenerationError,
    AITimeoutError,
    AIQuotaExceededError,
    AIInvalidKeyError,
    AIProviderError
)
from .utils import (
    SUPPORTED_PROVIDERS,
    PROVIDER_MODELS,
    get_model_string,
    get_available_providers,
    get_available_models,
    validate_provider,
    validate_model,
    estimate_cost
)

__all__ = [
    # Service
    'LLMService',
    'LLMResponse',
    # Exceptions
    'AIGenerationError',
    'AITimeoutError',
    'AIQuotaExceededError',
    'AIInvalidKeyError',
    'AIProviderError',
    # Utils
    'SUPPORTED_PROVIDERS',
    'PROVIDER_MODELS',
    'get_model_string',
    'get_available_providers',
    'get_available_models',
    'validate_provider',
    'validate_model',
    'estimate_cost',
]

