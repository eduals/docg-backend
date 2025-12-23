"""
Document Serializer.
"""

from typing import Any, Dict
from .base import BaseSerializer


class DocumentSerializer(BaseSerializer):
    """Serializer para GeneratedDocument."""

    def __init__(
        self,
        instance: Any = None,
        many: bool = False,
        include_workflow: bool = False,
        include_template: bool = False
    ):
        super().__init__(instance, many)
        self.include_workflow = include_workflow
        self.include_template = include_template

    def _serialize_one(self, instance: Any) -> Dict[str, Any]:
        """Serializa um documento."""
        result = {
            'id': str(instance.id),
            'organization_id': str(instance.organization_id),
            'workflow_id': str(instance.workflow_id) if instance.workflow_id else None,
            'template_id': str(instance.template_id) if instance.template_id else None,
            'execution_id': str(instance.execution_id) if instance.execution_id else None,
            'name': instance.name,
            'status': instance.status,
            'google_file_id': instance.google_file_id,
            'pdf_file_id': instance.pdf_file_id,
            'web_view_link': instance.web_view_link,
            'pdf_view_link': instance.pdf_view_link,
            'download_link': instance.download_link,
            'source_object_type': instance.source_object_type,
            'source_object_id': instance.source_object_id,
            'error_message': instance.error_message,
            'created_at': instance.created_at.isoformat() if instance.created_at else None,
            'updated_at': instance.updated_at.isoformat() if instance.updated_at else None,
        }

        if self.include_workflow and instance.workflow:
            result['workflow'] = {
                'id': str(instance.workflow.id),
                'name': instance.workflow.name,
            }

        if self.include_template and instance.template:
            result['template'] = {
                'id': str(instance.template.id),
                'name': instance.template.name,
            }

        return result
