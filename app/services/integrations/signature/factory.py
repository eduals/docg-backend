"""
Factory para criar adapters de providers de assinatura.
"""
from typing import Optional
from .base import SignatureProviderAdapter
from .clicksign import ClickSignAdapter
from .zapsign import ZapSignAdapter
import logging

logger = logging.getLogger(__name__)

class SignatureProviderFactory:
    """Factory para criar adapters de providers de assinatura"""
    
    _adapters = {
        'clicksign': ClickSignAdapter,
        'zapsign': ZapSignAdapter,
    }
    
    @classmethod
    def get_adapter(
        cls,
        provider: str,
        connection_id: str,
        organization_id: str
    ) -> SignatureProviderAdapter:
        """
        Cria adapter para o provider especificado.
        
        Args:
            provider: Nome do provider ('clicksign', 'zapsign')
            connection_id: ID da conexão DataSourceConnection
            organization_id: ID da organização
            
        Returns:
            SignatureProviderAdapter: Adapter do provider
            
        Raises:
            ValueError: Se provider não é suportado
        """
        provider = provider.lower()
        
        if provider not in cls._adapters:
            raise ValueError(
                f"Provider '{provider}' não é suportado. "
                f"Providers disponíveis: {', '.join(cls._adapters.keys())}"
            )
        
        adapter_class = cls._adapters[provider]
        
        try:
            return adapter_class(
                organization_id=organization_id,
                connection_id=connection_id
            )
        except Exception as e:
            logger.error(f"Erro ao criar adapter {provider}: {str(e)}")
            raise
    
    @classmethod
    def list_providers(cls) -> list[str]:
        """Retorna lista de providers suportados"""
        return list(cls._adapters.keys())
    
    @classmethod
    def is_provider_supported(cls, provider: str) -> bool:
        """Verifica se provider é suportado"""
        return provider.lower() in cls._adapters
