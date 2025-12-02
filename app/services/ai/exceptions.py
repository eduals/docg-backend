"""
Exceções customizadas para o serviço de IA.
"""


class AIGenerationError(Exception):
    """Erro genérico de geração de IA"""
    
    def __init__(self, message: str, provider: str = None, model: str = None):
        self.message = message
        self.provider = provider
        self.model = model
        super().__init__(self.message)
    
    def __str__(self):
        if self.provider and self.model:
            return f"[{self.provider}/{self.model}] {self.message}"
        return self.message


class AITimeoutError(AIGenerationError):
    """Timeout na chamada de IA"""
    
    def __init__(self, message: str = "Timeout na geração de texto", provider: str = None, model: str = None, timeout_seconds: int = None):
        self.timeout_seconds = timeout_seconds
        if timeout_seconds:
            message = f"{message} (timeout: {timeout_seconds}s)"
        super().__init__(message, provider, model)


class AIQuotaExceededError(AIGenerationError):
    """Quota de API excedida"""
    
    def __init__(self, message: str = "Quota de API excedida", provider: str = None, model: str = None):
        super().__init__(message, provider, model)


class AIInvalidKeyError(AIGenerationError):
    """API key inválida ou não autorizada"""
    
    def __init__(self, message: str = "API key inválida ou não autorizada", provider: str = None, model: str = None):
        super().__init__(message, provider, model)


class AIProviderError(AIGenerationError):
    """Erro específico do provedor de IA"""
    
    def __init__(self, message: str, provider: str = None, model: str = None, status_code: int = None):
        self.status_code = status_code
        super().__init__(message, provider, model)


class AIModelNotFoundError(AIGenerationError):
    """Modelo não encontrado ou não suportado"""
    
    def __init__(self, message: str = "Modelo não encontrado", provider: str = None, model: str = None):
        super().__init__(message, provider, model)


class AIContentFilterError(AIGenerationError):
    """Conteúdo bloqueado por filtros de segurança"""
    
    def __init__(self, message: str = "Conteúdo bloqueado por filtros de segurança", provider: str = None, model: str = None):
        super().__init__(message, provider, model)

