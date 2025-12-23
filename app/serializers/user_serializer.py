"""
User Serializer.
"""

from typing import Any, Dict
from .base import BaseSerializer


class UserSerializer(BaseSerializer):
    """Serializer para User."""

    # Campos sensíveis que nunca devem ser expostos
    SENSITIVE_FIELDS = ['password', 'password_hash', 'two_factor_secret']

    def __init__(
        self,
        instance: Any = None,
        many: bool = False,
        include_organization: bool = False
    ):
        super().__init__(instance, many)
        self.include_organization = include_organization

    def _serialize_one(self, instance: Any) -> Dict[str, Any]:
        """Serializa um usuário."""
        result = {
            'id': str(instance.id),
            'email': instance.email,
            'name': instance.name,
            'role': instance.role,
            'is_active': instance.is_active,
            'email_verified': instance.email_verified,
            'two_factor_enabled': instance.two_factor_enabled,
            'last_login_at': instance.last_login_at.isoformat() if instance.last_login_at else None,
            'created_at': instance.created_at.isoformat() if instance.created_at else None,
            'updated_at': instance.updated_at.isoformat() if instance.updated_at else None,
        }

        if self.include_organization and instance.organization:
            result['organization'] = {
                'id': str(instance.organization.id),
                'name': instance.organization.name,
                'plan': instance.organization.plan,
            }

        return result
