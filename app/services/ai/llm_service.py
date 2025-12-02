"""
Serviço unificado de LLM usando LiteLLM.

LiteLLM abstrai múltiplos provedores de IA com uma interface única,
suportando OpenAI, Gemini, Anthropic e 100+ outros modelos.
"""

import time
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass

import litellm
from litellm import completion, acompletion
from litellm.exceptions import (
    AuthenticationError,
    RateLimitError,
    Timeout,
    APIError,
    BadRequestError,
    NotFoundError,
)

from .exceptions import (
    AIGenerationError,
    AITimeoutError,
    AIQuotaExceededError,
    AIInvalidKeyError,
    AIProviderError,
    AIModelNotFoundError,
    AIContentFilterError,
)
from .utils import get_model_string, estimate_cost, validate_provider

# Configurar logging
logger = logging.getLogger('docugen.ai')

# Configurar LiteLLM para não logar mensagens verbosas
litellm.set_verbose = False


@dataclass
class LLMResponse:
    """Resposta do serviço de LLM"""
    text: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    time_ms: float
    estimated_cost_usd: float
    raw_response: Optional[Dict] = None
    
    def to_dict(self) -> Dict:
        return {
            'text': self.text,
            'provider': self.provider,
            'model': self.model,
            'input_tokens': self.input_tokens,
            'output_tokens': self.output_tokens,
            'total_tokens': self.total_tokens,
            'time_ms': self.time_ms,
            'estimated_cost_usd': self.estimated_cost_usd,
        }


class LLMService:
    """
    Serviço unificado para geração de texto via LLM.
    
    Usa LiteLLM para abstrair múltiplos provedores com interface única.
    
    Exemplo de uso:
        service = LLMService()
        response = service.generate_text(
            model="openai/gpt-4",
            prompt="Descreva o produto...",
            api_key="sk-...",
            temperature=0.7
        )
        print(response.text)
    """
    
    def __init__(self):
        """Inicializa o serviço de LLM"""
        self.default_temperature = 0.7
        self.default_max_tokens = 1000
        self.default_timeout = 60
    
    def generate_text(
        self,
        model: str,
        prompt: str,
        api_key: str,
        system_prompt: Optional[str] = None,
        temperature: float = None,
        max_tokens: int = None,
        timeout: int = None,
        **kwargs
    ) -> LLMResponse:
        """
        Gera texto usando LLM de forma síncrona.
        
        Args:
            model: Modelo no formato 'provider/model' (ex: 'openai/gpt-4')
            prompt: Prompt do usuário
            api_key: API key do provedor
            system_prompt: Prompt de sistema opcional
            temperature: Temperatura para geração (0.0 a 2.0)
            max_tokens: Máximo de tokens na resposta
            timeout: Timeout em segundos
            **kwargs: Argumentos adicionais para o modelo
        
        Returns:
            LLMResponse com o texto gerado e métricas
        
        Raises:
            AITimeoutError: Se timeout for excedido
            AIQuotaExceededError: Se quota do provedor for excedida
            AIInvalidKeyError: Se API key for inválida
            AIGenerationError: Para outros erros
        """
        temperature = temperature if temperature is not None else self.default_temperature
        max_tokens = max_tokens or self.default_max_tokens
        timeout = timeout or self.default_timeout
        
        # Extrair provider e model do formato 'provider/model'
        if '/' in model:
            provider, model_name = model.split('/', 1)
        else:
            provider = 'openai'
            model_name = model
        
        logger.info(f"[AI] Iniciando geração - provider={provider}, model={model_name}")
        start_time = time.time()
        
        # Construir mensagens
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        try:
            # Chamar LiteLLM
            response = completion(
                model=model,
                messages=messages,
                api_key=api_key,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
                **kwargs
            )
            
            duration_ms = (time.time() - start_time) * 1000
            
            # Extrair métricas
            usage = response.usage
            input_tokens = usage.prompt_tokens if usage else 0
            output_tokens = usage.completion_tokens if usage else 0
            total_tokens = usage.total_tokens if usage else 0
            
            # Extrair texto da resposta
            text = response.choices[0].message.content
            
            # Estimar custo
            cost = estimate_cost(provider, model_name, input_tokens, output_tokens)
            
            logger.info(
                f"[AI] Geração concluída - provider={provider}, model={model_name}, "
                f"tokens={total_tokens}, time_ms={duration_ms:.0f}, cost_usd={cost:.6f}"
            )
            
            return LLMResponse(
                text=text,
                provider=provider,
                model=model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                time_ms=duration_ms,
                estimated_cost_usd=cost,
                raw_response=response.model_dump() if hasattr(response, 'model_dump') else None
            )
            
        except Timeout as e:
            logger.warning(f"[AI] Timeout - provider={provider}, model={model_name}, timeout={timeout}s")
            raise AITimeoutError(
                message=str(e),
                provider=provider,
                model=model_name,
                timeout_seconds=timeout
            )
        
        except AuthenticationError as e:
            logger.error(f"[AI] Auth error - provider={provider}, model={model_name}")
            raise AIInvalidKeyError(
                message=str(e),
                provider=provider,
                model=model_name
            )
        
        except RateLimitError as e:
            logger.error(f"[AI] Rate limit - provider={provider}, model={model_name}")
            raise AIQuotaExceededError(
                message=str(e),
                provider=provider,
                model=model_name
            )
        
        except NotFoundError as e:
            logger.error(f"[AI] Model not found - provider={provider}, model={model_name}")
            raise AIModelNotFoundError(
                message=str(e),
                provider=provider,
                model=model_name
            )
        
        except BadRequestError as e:
            error_msg = str(e).lower()
            if 'content' in error_msg and ('filter' in error_msg or 'safety' in error_msg):
                logger.warning(f"[AI] Content filtered - provider={provider}, model={model_name}")
                raise AIContentFilterError(
                    message=str(e),
                    provider=provider,
                    model=model_name
                )
            raise AIProviderError(
                message=str(e),
                provider=provider,
                model=model_name,
                status_code=400
            )
        
        except APIError as e:
            logger.error(
                f"[AI] API error - provider={provider}, model={model_name}, "
                f"error={type(e).__name__}: {str(e)}"
            )
            raise AIProviderError(
                message=str(e),
                provider=provider,
                model=model_name,
                status_code=getattr(e, 'status_code', None)
            )
        
        except Exception as e:
            logger.error(
                f"[AI] Unexpected error - provider={provider}, model={model_name}, "
                f"error={type(e).__name__}: {str(e)}"
            )
            raise AIGenerationError(
                message=str(e),
                provider=provider,
                model=model_name
            )
    
    async def generate_text_async(
        self,
        model: str,
        prompt: str,
        api_key: str,
        system_prompt: Optional[str] = None,
        temperature: float = None,
        max_tokens: int = None,
        timeout: int = None,
        **kwargs
    ) -> LLMResponse:
        """
        Gera texto usando LLM de forma assíncrona.
        
        Mesmos parâmetros e retorno de generate_text().
        """
        temperature = temperature if temperature is not None else self.default_temperature
        max_tokens = max_tokens or self.default_max_tokens
        timeout = timeout or self.default_timeout
        
        if '/' in model:
            provider, model_name = model.split('/', 1)
        else:
            provider = 'openai'
            model_name = model
        
        logger.info(f"[AI] Iniciando geração async - provider={provider}, model={model_name}")
        start_time = time.time()
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = await acompletion(
                model=model,
                messages=messages,
                api_key=api_key,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
                **kwargs
            )
            
            duration_ms = (time.time() - start_time) * 1000
            
            usage = response.usage
            input_tokens = usage.prompt_tokens if usage else 0
            output_tokens = usage.completion_tokens if usage else 0
            total_tokens = usage.total_tokens if usage else 0
            
            text = response.choices[0].message.content
            cost = estimate_cost(provider, model_name, input_tokens, output_tokens)
            
            logger.info(
                f"[AI] Geração async concluída - provider={provider}, model={model_name}, "
                f"tokens={total_tokens}, time_ms={duration_ms:.0f}"
            )
            
            return LLMResponse(
                text=text,
                provider=provider,
                model=model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                time_ms=duration_ms,
                estimated_cost_usd=cost,
                raw_response=response.model_dump() if hasattr(response, 'model_dump') else None
            )
            
        except Timeout as e:
            raise AITimeoutError(str(e), provider, model_name, timeout)
        except AuthenticationError as e:
            raise AIInvalidKeyError(str(e), provider, model_name)
        except RateLimitError as e:
            raise AIQuotaExceededError(str(e), provider, model_name)
        except NotFoundError as e:
            raise AIModelNotFoundError(str(e), provider, model_name)
        except APIError as e:
            raise AIProviderError(str(e), provider, model_name, getattr(e, 'status_code', None))
        except Exception as e:
            raise AIGenerationError(str(e), provider, model_name)
    
    def validate_api_key(self, provider: str, api_key: str) -> Dict[str, Any]:
        """
        Valida se API key é válida fazendo uma chamada de teste.
        
        Args:
            provider: Nome do provedor (openai, gemini, anthropic)
            api_key: API key a ser validada
        
        Returns:
            Dict com 'valid' (bool), 'provider', 'message'
        """
        if not validate_provider(provider):
            return {
                'valid': False,
                'provider': provider,
                'message': f'Provedor não suportado: {provider}'
            }
        
        # Modelo de teste por provedor
        test_models = {
            'openai': 'openai/gpt-3.5-turbo',
            'gemini': 'gemini/gemini-1.5-flash',
            'anthropic': 'anthropic/claude-3-haiku-20240307',
        }
        
        model = test_models.get(provider.lower(), f'{provider}/test')
        
        try:
            # Fazer chamada mínima para validar
            response = completion(
                model=model,
                messages=[{"role": "user", "content": "Hi"}],
                api_key=api_key,
                max_tokens=5,
                timeout=30
            )
            
            return {
                'valid': True,
                'provider': provider,
                'message': 'API key válida'
            }
        
        except AuthenticationError:
            return {
                'valid': False,
                'provider': provider,
                'message': 'API key inválida ou não autorizada'
            }
        
        except RateLimitError:
            # Rate limit significa que a key é válida, só está limitada
            return {
                'valid': True,
                'provider': provider,
                'message': 'API key válida (rate limit atingido)'
            }
        
        except Exception as e:
            return {
                'valid': False,
                'provider': provider,
                'message': f'Erro ao validar: {str(e)}'
            }

