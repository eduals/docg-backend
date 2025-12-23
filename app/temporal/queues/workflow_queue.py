"""
Workflow Queue - Fila principal para execução de workflows.

Processa:
- Triggers (HubSpot, Google Forms)
- Coordenação geral do workflow
- Activities base (load, update, complete)
"""

from . import WORKFLOW_QUEUE

QUEUE_NAME = WORKFLOW_QUEUE

# Activities que rodam nesta queue
QUEUE_ACTIVITIES = [
    'load_execution',
    'update_current_node',
    'save_execution_context',
    'pause_execution',
    'resume_execution',
    'complete_execution',
    'fail_execution',
    'add_execution_log',
    'execute_trigger_node',
]

# Configurações específicas
QUEUE_CONFIG = {
    'max_concurrent_activities': 100,
    'max_concurrent_workflow_task_pollers': 4,
    'max_concurrent_activity_task_pollers': 4,
}
