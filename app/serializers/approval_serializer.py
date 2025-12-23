"""
Approval Serializer.
"""

from typing import Any, Dict
from .base import BaseSerializer


class ApprovalSerializer(BaseSerializer):
    """Serializer para Approval."""

    def __init__(
        self,
        instance: Any = None,
        many: bool = False,
        include_documents: bool = False,
        include_workflow: bool = False
    ):
        super().__init__(instance, many)
        self.include_documents = include_documents
        self.include_workflow = include_workflow

    def _serialize_one(self, instance: Any) -> Dict[str, Any]:
        """Serializa uma aprovação."""
        result = {
            'id': str(instance.id),
            'execution_id': str(instance.execution_id) if instance.execution_id else None,
            'workflow_id': str(instance.workflow_id) if instance.workflow_id else None,
            'status': instance.status,
            'approver_email': instance.approver_email,
            'approver_name': instance.approver_name,
            'decision': instance.decision,
            'decision_at': instance.decision_at.isoformat() if instance.decision_at else None,
            'comments': instance.comments,
            'expires_at': instance.expires_at.isoformat() if instance.expires_at else None,
            'token': instance.token,
            'created_at': instance.created_at.isoformat() if instance.created_at else None,
        }

        if self.include_documents and hasattr(instance, 'documents'):
            result['documents'] = [
                {
                    'id': str(doc.id),
                    'name': doc.name,
                    'web_view_link': doc.web_view_link,
                }
                for doc in instance.documents
            ]

        if self.include_workflow and instance.workflow:
            result['workflow'] = {
                'id': str(instance.workflow.id),
                'name': instance.workflow.name,
            }

        return result
