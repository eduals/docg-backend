"""
Task Queues do Temporal - Filas separadas por tipo de trabalho.

Seguindo padrão Automatisch, cada tipo de trabalho tem sua própria queue:
- WORKFLOW_QUEUE: Execução principal de workflows
- EMAIL_QUEUE: Envio de emails (Gmail, Outlook)
- WEBHOOK_QUEUE: Chamadas HTTP externas
- SIGNATURE_QUEUE: Integração com serviços de assinatura
- DOCUMENT_QUEUE: Geração de documentos
"""

import os

# Queue principal para workflows
WORKFLOW_QUEUE = os.getenv('TEMPORAL_WORKFLOW_QUEUE', 'docg-workflows')

# Queue para envio de emails
EMAIL_QUEUE = os.getenv('TEMPORAL_EMAIL_QUEUE', 'docg-emails')

# Queue para webhooks e chamadas HTTP
WEBHOOK_QUEUE = os.getenv('TEMPORAL_WEBHOOK_QUEUE', 'docg-webhooks')

# Queue para assinaturas (ClickSign, ZapSign)
SIGNATURE_QUEUE = os.getenv('TEMPORAL_SIGNATURE_QUEUE', 'docg-signatures')

# Queue para geração de documentos
DOCUMENT_QUEUE = os.getenv('TEMPORAL_DOCUMENT_QUEUE', 'docg-documents')

# Queue para aprovações
APPROVAL_QUEUE = os.getenv('TEMPORAL_APPROVAL_QUEUE', 'docg-approvals')


# Mapeamento de node types para queues
NODE_TYPE_QUEUE_MAP = {
    # Triggers
    'trigger': WORKFLOW_QUEUE,
    'hubspot': WORKFLOW_QUEUE,
    'webhook': WEBHOOK_QUEUE,
    'google-forms': WORKFLOW_QUEUE,

    # Documents
    'google-docs': DOCUMENT_QUEUE,
    'google-slides': DOCUMENT_QUEUE,
    'microsoft-word': DOCUMENT_QUEUE,
    'microsoft-powerpoint': DOCUMENT_QUEUE,

    # Email
    'gmail': EMAIL_QUEUE,
    'outlook': EMAIL_QUEUE,
    'send-email': EMAIL_QUEUE,

    # Signatures
    'clicksign': SIGNATURE_QUEUE,
    'zapsign': SIGNATURE_QUEUE,
    'request-signatures': SIGNATURE_QUEUE,

    # Approvals
    'approval': APPROVAL_QUEUE,
    'request-approval': APPROVAL_QUEUE,

    # Webhooks
    'send-webhook': WEBHOOK_QUEUE,
    'http-request': WEBHOOK_QUEUE,
}


def get_queue_for_node_type(node_type: str) -> str:
    """
    Retorna a queue apropriada para um tipo de node.

    Args:
        node_type: Tipo do node (ex: 'google-docs', 'gmail')

    Returns:
        Nome da task queue
    """
    return NODE_TYPE_QUEUE_MAP.get(node_type, WORKFLOW_QUEUE)


# Lista de todas as queues para inicialização
ALL_QUEUES = [
    WORKFLOW_QUEUE,
    EMAIL_QUEUE,
    WEBHOOK_QUEUE,
    SIGNATURE_QUEUE,
    DOCUMENT_QUEUE,
    APPROVAL_QUEUE,
]


__all__ = [
    'WORKFLOW_QUEUE',
    'EMAIL_QUEUE',
    'WEBHOOK_QUEUE',
    'SIGNATURE_QUEUE',
    'DOCUMENT_QUEUE',
    'APPROVAL_QUEUE',
    'NODE_TYPE_QUEUE_MAP',
    'get_queue_for_node_type',
    'ALL_QUEUES',
]
