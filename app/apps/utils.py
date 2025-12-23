"""
App Utilities - Funções utilitárias para apps.
"""

from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)


def get_connection_credentials(connection_id: str) -> Dict[str, Any]:
    """
    Obtém credenciais de uma conexão.

    Args:
        connection_id: ID da conexão

    Returns:
        Dict com credenciais (access_token, refresh_token, etc)
    """
    from app.models import DataSourceConnection

    connection = DataSourceConnection.query.get(connection_id)
    if not connection:
        raise ValueError(f"Connection {connection_id} not found")

    return connection.get_credentials()


def refresh_oauth_token(connection_id: str) -> Dict[str, Any]:
    """
    Atualiza token OAuth de uma conexão.

    Args:
        connection_id: ID da conexão

    Returns:
        Dict com novo token
    """
    from app.models import DataSourceConnection
    from app.database import db

    connection = DataSourceConnection.query.get(connection_id)
    if not connection:
        raise ValueError(f"Connection {connection_id} not found")

    # Implementar refresh baseado no tipo de conexão
    if connection.source_type == 'google':
        from app.services.google_oauth import refresh_google_token
        new_credentials = refresh_google_token(connection)
    elif connection.source_type == 'microsoft':
        from app.services.microsoft_oauth import refresh_microsoft_token
        new_credentials = refresh_microsoft_token(connection)
    elif connection.source_type == 'hubspot':
        from app.services.hubspot_oauth import refresh_hubspot_token
        new_credentials = refresh_hubspot_token(connection)
    else:
        raise ValueError(f"Unsupported source type: {connection.source_type}")

    # Atualizar credentials no banco
    connection.set_credentials(new_credentials)
    db.session.commit()

    return new_credentials


def list_available_apps() -> List[Dict[str, Any]]:
    """
    Lista todos os apps disponíveis.

    Returns:
        Lista de apps com name, key, description
    """
    from app.apps import AppRegistry

    apps = []
    for app in AppRegistry.list_all():
        apps.append({
            'key': app.key,
            'name': app.name,
            'description': app.description,
            'icon_url': app.icon_url,
            'auth_type': app.get_auth_config().auth_type.value if app.get_auth_config() else None,
            'actions_count': len(app.get_actions()),
            'triggers_count': len(app.get_triggers()),
        })

    return apps


def get_app_actions(app_key: str) -> List[Dict[str, Any]]:
    """
    Lista actions de um app.

    Args:
        app_key: Chave do app

    Returns:
        Lista de actions
    """
    from app.apps import AppRegistry

    app = AppRegistry.get(app_key)
    if not app:
        return []

    return [
        {
            'key': action.key,
            'name': action.name,
            'description': action.description,
            'parameters': action.parameters,
        }
        for action in app.get_actions()
    ]


def get_app_triggers(app_key: str) -> List[Dict[str, Any]]:
    """
    Lista triggers de um app.

    Args:
        app_key: Chave do app

    Returns:
        Lista de triggers
    """
    from app.apps import AppRegistry

    app = AppRegistry.get(app_key)
    if not app:
        return []

    return [
        {
            'key': trigger.key,
            'name': trigger.name,
            'description': trigger.description,
            'output_schema': trigger.output_schema,
        }
        for trigger in app.get_triggers()
    ]
