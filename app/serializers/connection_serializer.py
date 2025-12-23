"""
Connection Serializer.
"""

from typing import Any, Dict
from .base import BaseSerializer


class ConnectionSerializer(BaseSerializer):
    """Serializer para DataSourceConnection."""

    # Campos sensíveis que nunca devem ser expostos
    SENSITIVE_FIELDS = ['credentials', 'access_token', 'refresh_token', 'api_key']

    def __init__(
        self,
        instance: Any = None,
        many: bool = False,
        include_status: bool = True
    ):
        super().__init__(instance, many)
        self.include_status = include_status

    def _serialize_one(self, instance: Any) -> Dict[str, Any]:
        """Serializa uma conexão."""
        result = {
            'id': str(instance.id),
            'organization_id': str(instance.organization_id),
            'name': instance.name,
            'source_type': instance.source_type,
            'auth_type': instance.auth_type,
            'is_active': instance.is_active,
            'last_used_at': instance.last_used_at.isoformat() if instance.last_used_at else None,
            'created_at': instance.created_at.isoformat() if instance.created_at else None,
            'updated_at': instance.updated_at.isoformat() if instance.updated_at else None,
        }

        if self.include_status:
            result['status'] = self._get_connection_status(instance)

        return result

    def _get_connection_status(self, instance: Any) -> str:
        """Determina status da conexão."""
        if not instance.is_active:
            return 'inactive'

        # Verificar se tem credenciais válidas
        credentials = instance.get_credentials() if hasattr(instance, 'get_credentials') else {}
        if not credentials:
            return 'not_configured'

        # Verificar expiração de token se aplicável
        if instance.auth_type == 'oauth2':
            token_expires_at = credentials.get('token_expires_at')
            if token_expires_at:
                from datetime import datetime
                if datetime.fromisoformat(token_expires_at) < datetime.utcnow():
                    return 'token_expired'

        return 'connected'
