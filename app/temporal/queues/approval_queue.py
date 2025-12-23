"""
Approval Queue - Fila para aprovações.

Processa:
- Criação de solicitações de aprovação
- Expiração de aprovações
"""

from . import APPROVAL_QUEUE

QUEUE_NAME = APPROVAL_QUEUE

# Activities que rodam nesta queue
QUEUE_ACTIVITIES = [
    'create_approval',
    'expire_approval',
]

# Configurações específicas
QUEUE_CONFIG = {
    'max_concurrent_activities': 50,
    'max_concurrent_activity_task_pollers': 2,
}
