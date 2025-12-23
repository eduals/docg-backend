"""
Signature Queue - Fila para serviços de assinatura.

Processa:
- ClickSign
- ZapSign
- DocuSign (futuro)
"""

from . import SIGNATURE_QUEUE

QUEUE_NAME = SIGNATURE_QUEUE

# Activities que rodam nesta queue
QUEUE_ACTIVITIES = [
    'create_signature_request',
    'expire_signature',
]

# Configurações específicas
QUEUE_CONFIG = {
    'max_concurrent_activities': 25,
    'max_concurrent_activity_task_pollers': 2,
    # Signatures podem demorar
    'default_timeout_seconds': 300,
}
