"""
Node Serializer.
"""

from typing import Any, Dict
from .base import BaseSerializer


class NodeSerializer(BaseSerializer):
    """Serializer para WorkflowNode."""

    def __init__(
        self,
        instance: Any = None,
        many: bool = False,
        include_config: bool = True
    ):
        super().__init__(instance, many)
        self.include_config = include_config

    def _serialize_one(self, instance: Any) -> Dict[str, Any]:
        """Serializa um node."""
        result = {
            'id': str(instance.id),
            'workflow_id': str(instance.workflow_id),
            'node_type': instance.node_type,
            'position': instance.position,
            'parent_node_id': str(instance.parent_node_id) if instance.parent_node_id else None,
            'status': instance.status,
            'created_at': instance.created_at.isoformat() if instance.created_at else None,
            'updated_at': instance.updated_at.isoformat() if instance.updated_at else None,
        }

        if self.include_config:
            result['config'] = instance.config or {}

            # Adicionar webhook_token se for webhook trigger
            if instance.node_type == 'webhook' and instance.webhook_token:
                result['webhook_token'] = instance.webhook_token

        return result
