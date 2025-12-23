"""
Signature Serializer.
"""

from typing import Any, Dict
from .base import BaseSerializer


class SignatureSerializer(BaseSerializer):
    """Serializer para SignatureRequest."""

    def __init__(
        self,
        instance: Any = None,
        many: bool = False,
        include_signers: bool = True,
        include_documents: bool = False
    ):
        super().__init__(instance, many)
        self.include_signers = include_signers
        self.include_documents = include_documents

    def _serialize_one(self, instance: Any) -> Dict[str, Any]:
        """Serializa uma solicitação de assinatura."""
        result = {
            'id': str(instance.id),
            'execution_id': str(instance.execution_id) if instance.execution_id else None,
            'workflow_id': str(instance.workflow_id) if instance.workflow_id else None,
            'provider': instance.provider,
            'external_id': instance.external_id,
            'status': instance.status,
            'expires_at': instance.expires_at.isoformat() if instance.expires_at else None,
            'completed_at': instance.completed_at.isoformat() if instance.completed_at else None,
            'signed_document_url': instance.signed_document_url,
            'created_at': instance.created_at.isoformat() if instance.created_at else None,
        }

        if self.include_signers and hasattr(instance, 'signers'):
            result['signers'] = [
                SignerSerializer.to_dict(signer)
                for signer in instance.signers
            ]

        if self.include_documents and hasattr(instance, 'documents'):
            result['documents'] = [
                {
                    'id': str(doc.id),
                    'name': doc.name,
                }
                for doc in instance.documents
            ]

        return result


class SignerSerializer(BaseSerializer):
    """Serializer para Signer."""

    def _serialize_one(self, instance: Any) -> Dict[str, Any]:
        """Serializa um signatário."""
        return {
            'id': str(instance.id),
            'email': instance.email,
            'name': instance.name,
            'role': instance.role,
            'status': instance.status,
            'signed_at': instance.signed_at.isoformat() if instance.signed_at else None,
            'order': instance.order,
        }
