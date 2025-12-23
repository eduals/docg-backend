"""
Execution Serializer.
"""

from typing import Any, Dict, List
from .base import BaseSerializer


class ExecutionSerializer(BaseSerializer):
    """Serializer para WorkflowExecution."""

    def __init__(
        self,
        instance: Any = None,
        many: bool = False,
        include_logs: bool = False,
        include_workflow: bool = False,
        include_current_node: bool = True
    ):
        super().__init__(instance, many)
        self.include_logs = include_logs
        self.include_workflow = include_workflow
        self.include_current_node = include_current_node

    def _serialize_one(self, instance: Any) -> Dict[str, Any]:
        """Serializa uma execução."""
        # Mapear status do backend para interface
        status_mapping = {
            'completed': 'success',
            'failed': 'error',
            'running': 'running',
            'paused': 'paused',
            'pending': 'pending',
            # Novos status (F1)
            'queued': 'queued',
            'needs_review': 'needs_review',
            'ready': 'ready',
            'sending': 'sending',
            'sent': 'sent',
            'signing': 'signing',
            'signed': 'signed',
            'canceled': 'canceled'
        }
        interface_status = status_mapping.get(instance.status, instance.status)

        result = {
            'id': str(instance.id),
            'workflow_id': str(instance.workflow_id),
            'status': interface_status,

            # === Run State (F1) ===
            'progress': instance.progress,
            'current_step': instance.current_step,

            # Erros
            'error_message': instance.error_message,  # DEPRECATED
            'last_error_human': instance.last_error_human,
            'last_error_tech': instance.last_error_tech,

            # Preflight
            'preflight_summary': instance.preflight_summary,

            # Estados agregados
            'delivery_state': instance.delivery_state,
            'signature_state': instance.signature_state,

            # Ações recomendadas
            'recommended_actions': instance.recommended_actions,

            # === Observabilidade (F14) ===
            'phase_metrics': instance.phase_metrics,
            'correlation_id': str(instance.correlation_id) if instance.correlation_id else None,

            # === Campos existentes ===
            'started_at': instance.started_at.isoformat() if instance.started_at else None,
            'completed_at': instance.completed_at.isoformat() if instance.completed_at else None,
            'duration_ms': instance.execution_time_ms,
            'trigger_source': instance.trigger_type or 'manual',
            'trigger_data': instance.trigger_data,
            'generated_document_id': str(instance.generated_document_id) if instance.generated_document_id else None,
            'ai_metrics': instance.ai_metrics,
            'temporal_workflow_id': instance.temporal_workflow_id,
            'temporal_run_id': instance.temporal_run_id,
        }

        if self.include_current_node and instance.current_node_id:
            result['current_node_id'] = str(instance.current_node_id)

        if self.include_logs:
            result['execution_logs'] = instance.execution_logs or []

        if self.include_workflow and instance.workflow:
            result['workflow'] = {
                'id': str(instance.workflow.id),
                'name': instance.workflow.name,
            }

        return result
