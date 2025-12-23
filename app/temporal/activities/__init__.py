"""
Activities do Temporal - Unidades de trabalho executadas pelo Worker.

Cada activity representa uma operação específica:
- base: Activities utilitárias (load, update, pause, resume)
- trigger: Extração de dados de fontes (HubSpot, Webhook)
- document: Geração de documentos (Google Docs, Slides, Word, PowerPoint)
- approval: Criação e gerenciamento de aprovações
- signature: Envio para assinatura e rastreamento
- email: Envio de emails (Gmail, Outlook)
- webhook: Envio de webhooks de saída
- engine_bridge: Ponte para integração com a nova Engine
"""

from .base import (
    load_execution,
    update_current_node,
    save_execution_context,
    pause_execution,
    resume_execution,
    complete_execution,
    fail_execution,
    add_execution_log,
)
from .trigger import execute_trigger_node
from .document import execute_document_node
from .approval import create_approval, expire_approval
from .signature import create_signature_request, expire_signature
from .email import execute_email_node
from .webhook import execute_webhook_node

# Engine Bridge - funções auxiliares para usar a nova Engine
from .engine_bridge import (
    create_execution_step,
    start_execution_step,
    complete_execution_step,
    fail_execution_step,
    get_previous_steps_output,
    apply_compute_parameters,
    get_app_for_node,
    execute_via_app,
    build_global_variable_context,
    with_execution_step,
)

# Lista de todas as activities para registrar no Worker
ALL_ACTIVITIES = [
    # Base
    load_execution,
    update_current_node,
    save_execution_context,
    pause_execution,
    resume_execution,
    complete_execution,
    fail_execution,
    add_execution_log,
    # Trigger
    execute_trigger_node,
    # Document
    execute_document_node,
    # Approval
    create_approval,
    expire_approval,
    # Signature
    create_signature_request,
    expire_signature,
    # Email
    execute_email_node,
    # Webhook
    execute_webhook_node,
]

__all__ = [
    # Activities
    'load_execution',
    'update_current_node',
    'save_execution_context',
    'pause_execution',
    'resume_execution',
    'complete_execution',
    'fail_execution',
    'add_execution_log',
    'execute_trigger_node',
    'execute_document_node',
    'create_approval',
    'expire_approval',
    'create_signature_request',
    'expire_signature',
    'execute_email_node',
    'execute_webhook_node',
    'ALL_ACTIVITIES',
    # Engine Bridge
    'create_execution_step',
    'start_execution_step',
    'complete_execution_step',
    'fail_execution_step',
    'get_previous_steps_output',
    'apply_compute_parameters',
    'get_app_for_node',
    'execute_via_app',
    'build_global_variable_context',
    'with_execution_step',
]

