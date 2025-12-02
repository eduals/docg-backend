"""
Testes para app/services/ai/utils.py
"""

import pytest
from app.services.ai.utils import (
    get_model_string,
    get_available_providers,
    get_available_models,
    validate_provider,
    validate_model,
    estimate_cost,
    normalize_provider_name,
    SUPPORTED_PROVIDERS,
    PROVIDER_MODELS
)


class TestGetModelString:
    """Testes para get_model_string()"""
    
    def test_openai_model(self):
        result = get_model_string('openai', 'gpt-4')
        assert result == 'openai/gpt-4'
    
    def test_gemini_model(self):
        result = get_model_string('gemini', 'gemini-1.5-pro')
        assert result == 'gemini/gemini-1.5-pro'
    
    def test_anthropic_model(self):
        result = get_model_string('anthropic', 'claude-3-opus')
        assert result == 'anthropic/claude-3-opus'
    
    def test_case_insensitive_provider(self):
        result = get_model_string('OpenAI', 'gpt-4')
        assert result == 'openai/gpt-4'
    
    def test_strips_whitespace(self):
        result = get_model_string(' openai ', ' gpt-4 ')
        assert result == 'openai/gpt-4'


class TestGetAvailableProviders:
    """Testes para get_available_providers()"""
    
    def test_returns_list(self):
        result = get_available_providers()
        assert isinstance(result, list)
    
    def test_has_required_providers(self):
        result = get_available_providers()
        provider_ids = [p['id'] for p in result]
        assert 'openai' in provider_ids
        assert 'gemini' in provider_ids
        assert 'anthropic' in provider_ids
    
    def test_provider_structure(self):
        result = get_available_providers()
        for provider in result:
            assert 'id' in provider
            assert 'name' in provider
            assert 'models' in provider
            assert isinstance(provider['models'], list)


class TestGetAvailableModels:
    """Testes para get_available_models()"""
    
    def test_openai_models(self):
        models = get_available_models('openai')
        assert 'gpt-4' in models
        assert 'gpt-3.5-turbo' in models
    
    def test_gemini_models(self):
        models = get_available_models('gemini')
        assert 'gemini-1.5-pro' in models
    
    def test_unknown_provider_returns_empty(self):
        models = get_available_models('unknown')
        assert models == []
    
    def test_case_insensitive(self):
        models = get_available_models('OPENAI')
        assert len(models) > 0


class TestValidateProvider:
    """Testes para validate_provider()"""
    
    def test_valid_providers(self):
        assert validate_provider('openai') is True
        assert validate_provider('gemini') is True
        assert validate_provider('anthropic') is True
    
    def test_invalid_provider(self):
        assert validate_provider('unknown') is False
        assert validate_provider('') is False
    
    def test_case_insensitive(self):
        assert validate_provider('OpenAI') is True
        assert validate_provider('GEMINI') is True


class TestValidateModel:
    """Testes para validate_model()"""
    
    def test_valid_models(self):
        assert validate_model('openai', 'gpt-4') is True
        assert validate_model('gemini', 'gemini-1.5-pro') is True
    
    def test_invalid_model(self):
        assert validate_model('openai', 'invalid-model') is False
    
    def test_partial_match(self):
        # Modelos com versões específicas devem funcionar
        assert validate_model('openai', 'gpt-4-0613') is True


class TestEstimateCost:
    """Testes para estimate_cost()"""
    
    def test_returns_float(self):
        cost = estimate_cost('openai', 'gpt-4', 100, 50)
        assert isinstance(cost, float)
    
    def test_cost_is_positive(self):
        cost = estimate_cost('openai', 'gpt-4', 1000, 500)
        assert cost > 0
    
    def test_more_tokens_higher_cost(self):
        cost_low = estimate_cost('openai', 'gpt-4', 100, 50)
        cost_high = estimate_cost('openai', 'gpt-4', 1000, 500)
        assert cost_high > cost_low
    
    def test_unknown_model_uses_default(self):
        cost = estimate_cost('openai', 'unknown-model', 100, 50)
        assert cost > 0


class TestNormalizeProviderName:
    """Testes para normalize_provider_name()"""
    
    def test_lowercase(self):
        assert normalize_provider_name('OpenAI') == 'openai'
        assert normalize_provider_name('GEMINI') == 'gemini'
    
    def test_aliases(self):
        assert normalize_provider_name('gpt') == 'openai'
        assert normalize_provider_name('chatgpt') == 'openai'
        assert normalize_provider_name('google') == 'gemini'
        assert normalize_provider_name('claude') == 'anthropic'
    
    def test_strips_whitespace(self):
        assert normalize_provider_name(' openai ') == 'openai'

