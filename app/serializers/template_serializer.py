"""
Template Serializer.
"""

from typing import Any, Dict, List
from .base import BaseSerializer


class TemplateSerializer(BaseSerializer):
    """Serializer para Template."""

    def __init__(
        self,
        instance: Any = None,
        many: bool = False,
        include_tags: bool = False,
        include_connection: bool = False
    ):
        super().__init__(instance, many)
        self.include_tags = include_tags
        self.include_connection = include_connection

    def _serialize_one(self, instance: Any) -> Dict[str, Any]:
        """Serializa um template."""
        result = {
            'id': str(instance.id),
            'organization_id': str(instance.organization_id),
            'name': instance.name,
            'description': instance.description,
            'google_file_type': instance.google_file_type,
            'source_type': instance.source_type,
            'google_file_id': instance.google_file_id,
            'microsoft_file_id': instance.microsoft_file_id,
            'thumbnail_url': instance.thumbnail_url,
            'web_view_link': instance.web_view_link,
            'tags_synced': instance.tags_synced,
            'tags_synced_at': instance.tags_synced_at.isoformat() if instance.tags_synced_at else None,
            'created_at': instance.created_at.isoformat() if instance.created_at else None,
            'updated_at': instance.updated_at.isoformat() if instance.updated_at else None,
        }

        if self.include_tags:
            result['tags'] = [
                {
                    'id': str(tag.id),
                    'tag_name': tag.tag_name,
                    'tag_type': tag.tag_type,
                    'default_value': tag.default_value,
                }
                for tag in instance.tags
            ]

        if self.include_connection and instance.connection:
            result['connection'] = {
                'id': str(instance.connection.id),
                'name': instance.connection.name,
                'source_type': instance.connection.source_type,
            }

        return result
