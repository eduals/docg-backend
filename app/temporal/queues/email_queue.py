"""
Email Queue - Fila para envio de emails.

Processa:
- Gmail (via API)
- Outlook (via Microsoft Graph)
"""

from . import EMAIL_QUEUE

QUEUE_NAME = EMAIL_QUEUE

# Activities que rodam nesta queue
QUEUE_ACTIVITIES = [
    'execute_email_node',
]

# Configurações específicas
QUEUE_CONFIG = {
    'max_concurrent_activities': 50,
    'max_concurrent_activity_task_pollers': 2,
    # Rate limiting para evitar throttling das APIs
    'activities_per_second': 10,
}
