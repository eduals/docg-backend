"""
Testes para app/services/ai/exceptions.py
"""

import pytest
from app.services.ai.exceptions import (
    AIGenerationError,
    AITimeoutError,
    AIQuotaExceededError,
    AIInvalidKeyError,
    AIProviderError,
    AIModelNotFoundError,
    AIContentFilterError
)


class TestAIGenerationError:
    """Testes para AIGenerationError"""
    
    def test_basic_error(self):
        error = AIGenerationError("Test error")
        assert str(error) == "Test error"
    
    def test_with_provider_and_model(self):
        error = AIGenerationError("Test error", provider="openai", model="gpt-4")
        assert str(error) == "[openai/gpt-4] Test error"
    
    def test_attributes(self):
        error = AIGenerationError("Test", provider="openai", model="gpt-4")
        assert error.provider == "openai"
        assert error.model == "gpt-4"
        assert error.message == "Test"


class TestAITimeoutError:
    """Testes para AITimeoutError"""
    
    def test_inherits_from_generation_error(self):
        error = AITimeoutError()
        assert isinstance(error, AIGenerationError)
    
    def test_default_message(self):
        error = AITimeoutError()
        assert "Timeout" in str(error)
    
    def test_with_timeout_seconds(self):
        error = AITimeoutError(timeout_seconds=60)
        assert "60s" in str(error)


class TestAIQuotaExceededError:
    """Testes para AIQuotaExceededError"""
    
    def test_inherits_from_generation_error(self):
        error = AIQuotaExceededError()
        assert isinstance(error, AIGenerationError)
    
    def test_default_message(self):
        error = AIQuotaExceededError()
        assert "Quota" in str(error) or "quota" in str(error)


class TestAIInvalidKeyError:
    """Testes para AIInvalidKeyError"""
    
    def test_inherits_from_generation_error(self):
        error = AIInvalidKeyError()
        assert isinstance(error, AIGenerationError)
    
    def test_default_message(self):
        error = AIInvalidKeyError()
        assert "key" in str(error).lower()


class TestAIProviderError:
    """Testes para AIProviderError"""
    
    def test_with_status_code(self):
        error = AIProviderError("Server error", status_code=500)
        assert error.status_code == 500
    
    def test_inherits_from_generation_error(self):
        error = AIProviderError("Error")
        assert isinstance(error, AIGenerationError)


class TestAIModelNotFoundError:
    """Testes para AIModelNotFoundError"""
    
    def test_default_message(self):
        error = AIModelNotFoundError()
        assert "Modelo" in str(error) or "not found" in str(error).lower()


class TestAIContentFilterError:
    """Testes para AIContentFilterError"""
    
    def test_default_message(self):
        error = AIContentFilterError()
        assert "filtro" in str(error).lower() or "filter" in str(error).lower()

