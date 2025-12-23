"""
Document Queue - Fila para geração de documentos.

Processa:
- Google Docs (copy, replace tags, export)
- Google Slides (copy, replace tags, export)
- Microsoft Word (copy, replace tags, export)
- Microsoft PowerPoint (copy, replace tags, export)
"""

from . import DOCUMENT_QUEUE

QUEUE_NAME = DOCUMENT_QUEUE

# Activities que rodam nesta queue
QUEUE_ACTIVITIES = [
    'execute_document_node',
]

# Configurações específicas
QUEUE_CONFIG = {
    'max_concurrent_activities': 25,
    'max_concurrent_activity_task_pollers': 2,
    # Documentos podem ser grandes
    'default_timeout_seconds': 600,
}
