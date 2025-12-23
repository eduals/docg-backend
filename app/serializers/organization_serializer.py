"""
Organization Serializer.
"""

from typing import Any, Dict
from .base import BaseSerializer


class OrganizationSerializer(BaseSerializer):
    """Serializer para Organization."""

    def __init__(
        self,
        instance: Any = None,
        many: bool = False,
        include_usage: bool = False,
        include_settings: bool = False
    ):
        super().__init__(instance, many)
        self.include_usage = include_usage
        self.include_settings = include_settings

    def _serialize_one(self, instance: Any) -> Dict[str, Any]:
        """Serializa uma organização."""
        result = {
            'id': str(instance.id),
            'name': instance.name,
            'slug': instance.slug,
            'plan': instance.plan,
            'status': instance.status,
            'created_at': instance.created_at.isoformat() if instance.created_at else None,
            'updated_at': instance.updated_at.isoformat() if instance.updated_at else None,
        }

        if self.include_usage:
            result['usage'] = {
                'workflows_count': instance.workflows_count,
                'workflows_limit': instance.workflows_limit,
                'documents_generated_count': instance.documents_generated_count,
                'documents_limit': instance.documents_limit,
                'ai_tokens_used': instance.ai_tokens_used,
                'ai_tokens_limit': instance.ai_tokens_limit,
            }

        if self.include_settings:
            result['settings'] = instance.settings or {}

        return result
