"""
Workflow Serializer.
"""

from typing import Any, Dict, List, Optional
from .base import BaseSerializer


class WorkflowSerializer(BaseSerializer):
    """Serializer para Workflow."""

    fields = [
        'id', 'name', 'description', 'status',
        'source_connection_id', 'source_object_type',
        'template_id', 'output_folder_id', 'output_name_template',
        'create_pdf', 'trigger_type', 'trigger_config',
        'post_actions', 'created_at', 'updated_at'
    ]

    def __init__(
        self,
        instance: Any = None,
        many: bool = False,
        include_mappings: bool = False,
        include_ai_mappings: bool = False,
        include_nodes: bool = False,
        include_template: bool = True
    ):
        super().__init__(instance, many)
        self.include_mappings = include_mappings
        self.include_ai_mappings = include_ai_mappings
        self.include_nodes = include_nodes
        self.include_template = include_template

    def _serialize_one(self, instance: Any) -> Dict[str, Any]:
        """Serializa um workflow."""
        result = {
            'id': str(instance.id),
            'name': instance.name,
            'description': instance.description,
            'status': instance.status,
            'post_actions': instance.post_actions,
            'created_at': instance.created_at.isoformat() if instance.created_at else None,
            'updated_at': instance.updated_at.isoformat() if instance.updated_at else None,
            # Campos legados
            'source_connection_id': str(instance.source_connection_id) if instance.source_connection_id else None,
            'source_object_type': instance.source_object_type,
            'template_id': str(instance.template_id) if instance.template_id else None,
            'output_folder_id': instance.output_folder_id,
            'output_name_template': instance.output_name_template,
            'create_pdf': instance.create_pdf,
            'trigger_type': instance.trigger_type,
            'trigger_config': instance.trigger_config,
        }

        if self.include_mappings:
            result['field_mappings'] = [
                FieldMappingSerializer.to_dict(m)
                for m in instance.field_mappings
            ]

        if self.include_ai_mappings:
            result['ai_mappings'] = [m.to_dict() for m in instance.ai_mappings]

        if self.include_nodes:
            from .node_serializer import NodeSerializer
            result['nodes'] = NodeSerializer.to_list(
                instance.nodes.order_by('position').all()
            )

        if self.include_template and instance.template:
            result['template'] = {
                'id': str(instance.template.id),
                'name': instance.template.name,
                'google_file_type': instance.template.google_file_type,
                'thumbnail_url': instance.template.thumbnail_url
            }

        return result


class FieldMappingSerializer(BaseSerializer):
    """Serializer para WorkflowFieldMapping."""

    def _serialize_one(self, instance: Any) -> Dict[str, Any]:
        return {
            'id': str(instance.id),
            'template_tag': instance.template_tag,
            'source_field': instance.source_field,
            'transform_type': instance.transform_type,
            'transform_config': instance.transform_config,
            'default_value': instance.default_value
        }
