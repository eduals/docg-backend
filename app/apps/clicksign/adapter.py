"""
ClickSign Adapter - Wrapper para o adapter existente.

Este módulo fornece acesso ao ClickSignAdapter existente
através da nova estrutura de apps.
"""

# Re-exportar do serviço existente
from app.services.integrations.signature.clicksign import ClickSignAdapter

__all__ = ['ClickSignAdapter']
