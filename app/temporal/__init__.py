"""
Temporal - Execução assíncrona e durável de workflows.

Este módulo implementa a integração com Temporal.io para:
- Execução durável de workflows (sobrevive a restarts)
- Pausar/retomar em nodes de aprovação e assinatura
- Expiração via timers nativos (sem jobs de varredura)
- Retry automático de activities com falha

Estrutura:
- client.py: Cliente para conectar ao Temporal Server
- config.py: Configurações e constantes
- worker.py: Worker que executa workflows/activities
- workflows/: Definições de workflows
- activities/: Definições de activities
"""

from .config import TemporalConfig
from .client import get_temporal_client, send_signal

__all__ = [
    'TemporalConfig',
    'get_temporal_client',
    'send_signal',
]


