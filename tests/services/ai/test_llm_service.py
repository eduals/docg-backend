"""
Testes para app/services/ai/llm_service.py

Nota: Estes testes usam mocks para evitar chamadas reais à API.
Para testes de integração com APIs reais, use variáveis de ambiente.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from app.services.ai.llm_service import LLMService, LLMResponse
from app.services.ai.exceptions import (
    AIGenerationError,
    AITimeoutError,
    AIQuotaExceededError,
    AIInvalidKeyError
)


class TestLLMResponse:
    """Testes para LLMResponse"""
    
    def test_to_dict(self):
        response = LLMResponse(
            text="Generated text",
            provider="openai",
            model="gpt-4",
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            time_ms=1500.0,
            estimated_cost_usd=0.0045
        )
        
        result = response.to_dict()
        
        assert result['text'] == "Generated text"
        assert result['provider'] == "openai"
        assert result['model'] == "gpt-4"
        assert result['total_tokens'] == 150
        assert result['time_ms'] == 1500.0


class TestLLMService:
    """Testes para LLMService"""
    
    def test_init(self):
        service = LLMService()
        assert service.default_temperature == 0.7
        assert service.default_max_tokens == 1000
        assert service.default_timeout == 60
    
    @patch('app.services.ai.llm_service.completion')
    def test_generate_text_success(self, mock_completion):
        """Testa geração de texto com sucesso"""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Generated text"
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50
        mock_response.usage.total_tokens = 150
        mock_response.model_dump.return_value = {}
        mock_completion.return_value = mock_response
        
        service = LLMService()
        result = service.generate_text(
            model="openai/gpt-4",
            prompt="Test prompt",
            api_key="test-key"
        )
        
        assert isinstance(result, LLMResponse)
        assert result.text == "Generated text"
        assert result.provider == "openai"
        assert result.model == "gpt-4"
        assert result.total_tokens == 150
        
        # Verify completion was called correctly
        mock_completion.assert_called_once()
        call_kwargs = mock_completion.call_args.kwargs
        assert call_kwargs['model'] == 'openai/gpt-4'
        assert call_kwargs['api_key'] == 'test-key'
    
    @patch('app.services.ai.llm_service.completion')
    def test_generate_text_with_system_prompt(self, mock_completion):
        """Testa geração com system prompt"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Response"
        mock_response.usage.prompt_tokens = 50
        mock_response.usage.completion_tokens = 25
        mock_response.usage.total_tokens = 75
        mock_completion.return_value = mock_response
        
        service = LLMService()
        service.generate_text(
            model="openai/gpt-4",
            prompt="User prompt",
            api_key="test-key",
            system_prompt="You are helpful."
        )
        
        call_kwargs = mock_completion.call_args.kwargs
        messages = call_kwargs['messages']
        assert len(messages) == 2
        assert messages[0]['role'] == 'system'
        assert messages[1]['role'] == 'user'
    
    @patch('app.services.ai.llm_service.completion')
    def test_generate_text_timeout_error(self, mock_completion):
        """Testa tratamento de timeout"""
        from litellm.exceptions import Timeout
        mock_completion.side_effect = Timeout("Timeout occurred")
        
        service = LLMService()
        
        with pytest.raises(AITimeoutError):
            service.generate_text(
                model="openai/gpt-4",
                prompt="Test",
                api_key="test-key"
            )
    
    @patch('app.services.ai.llm_service.completion')
    def test_generate_text_auth_error(self, mock_completion):
        """Testa tratamento de erro de autenticação"""
        from litellm.exceptions import AuthenticationError
        mock_completion.side_effect = AuthenticationError("Invalid key")
        
        service = LLMService()
        
        with pytest.raises(AIInvalidKeyError):
            service.generate_text(
                model="openai/gpt-4",
                prompt="Test",
                api_key="invalid-key"
            )
    
    @patch('app.services.ai.llm_service.completion')
    def test_generate_text_rate_limit_error(self, mock_completion):
        """Testa tratamento de rate limit"""
        from litellm.exceptions import RateLimitError
        mock_completion.side_effect = RateLimitError("Rate limited")
        
        service = LLMService()
        
        with pytest.raises(AIQuotaExceededError):
            service.generate_text(
                model="openai/gpt-4",
                prompt="Test",
                api_key="test-key"
            )
    
    @patch('app.services.ai.llm_service.completion')
    def test_validate_api_key_valid(self, mock_completion):
        """Testa validação de API key válida"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hi"
        mock_completion.return_value = mock_response
        
        service = LLMService()
        result = service.validate_api_key('openai', 'valid-key')
        
        assert result['valid'] is True
        assert result['provider'] == 'openai'
    
    @patch('app.services.ai.llm_service.completion')
    def test_validate_api_key_invalid(self, mock_completion):
        """Testa validação de API key inválida"""
        from litellm.exceptions import AuthenticationError
        mock_completion.side_effect = AuthenticationError("Invalid")
        
        service = LLMService()
        result = service.validate_api_key('openai', 'invalid-key')
        
        assert result['valid'] is False
        assert 'inválida' in result['message'].lower() or 'invalid' in result['message'].lower()
    
    def test_validate_api_key_unsupported_provider(self):
        """Testa validação com provider não suportado"""
        service = LLMService()
        result = service.validate_api_key('unsupported', 'key')
        
        assert result['valid'] is False
        assert 'suportado' in result['message'].lower() or 'supported' in result['message'].lower()


class TestLLMServiceModelParsing:
    """Testes para parsing de modelo"""
    
    @patch('app.services.ai.llm_service.completion')
    def test_model_with_provider_prefix(self, mock_completion):
        """Testa modelo com prefixo provider/model"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15
        mock_completion.return_value = mock_response
        
        service = LLMService()
        result = service.generate_text(
            model="gemini/gemini-1.5-pro",
            prompt="Test",
            api_key="test"
        )
        
        assert result.provider == "gemini"
        assert result.model == "gemini-1.5-pro"
    
    @patch('app.services.ai.llm_service.completion')
    def test_model_without_prefix_defaults_to_openai(self, mock_completion):
        """Testa modelo sem prefixo (default OpenAI)"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15
        mock_completion.return_value = mock_response
        
        service = LLMService()
        result = service.generate_text(
            model="gpt-4",
            prompt="Test",
            api_key="test"
        )
        
        assert result.provider == "openai"
        assert result.model == "gpt-4"

