"""
Webhook Queue - Fila para chamadas HTTP externas.

Processa:
- Webhooks de saída
- HTTP requests customizados
"""

from . import WEBHOOK_QUEUE

QUEUE_NAME = WEBHOOK_QUEUE

# Activities que rodam nesta queue
QUEUE_ACTIVITIES = [
    'execute_webhook_node',
]

# Configurações específicas
QUEUE_CONFIG = {
    'max_concurrent_activities': 100,
    'max_concurrent_activity_task_pollers': 4,
    # Timeout maior para requests externos
    'default_timeout_seconds': 120,
}
