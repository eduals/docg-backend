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
- worker.py: Worker único (legacy)
- workers/: Workers dedicados por tipo
- queues/: Task queues separadas
- workflows/: Definições de workflows
- activities/: Definições de activities
"""

from .config import TemporalConfig
from .client import get_temporal_client, send_signal
from .queues import (
    WORKFLOW_QUEUE,
    EMAIL_QUEUE,
    WEBHOOK_QUEUE,
    SIGNATURE_QUEUE,
    DOCUMENT_QUEUE,
    APPROVAL_QUEUE,
    get_queue_for_node_type,
)

__all__ = [
    'TemporalConfig',
    'get_temporal_client',
    'send_signal',
    # Queues
    'WORKFLOW_QUEUE',
    'EMAIL_QUEUE',
    'WEBHOOK_QUEUE',
    'SIGNATURE_QUEUE',
    'DOCUMENT_QUEUE',
    'APPROVAL_QUEUE',
    'get_queue_for_node_type',
]


