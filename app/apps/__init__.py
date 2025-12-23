"""
DocG Apps - Sistema Modular de Apps.

Este módulo fornece um registry central de todos os apps disponíveis,
seguindo os padrões do Automatisch.

Uso:
    from app.apps import AppRegistry

    # Obter um app pelo key
    hubspot = AppRegistry.get('hubspot')

    # Listar todos os apps
    all_apps = AppRegistry.list_all()

    # Obter actions de um app
    actions = hubspot.get_actions()
"""

from typing import Dict, Optional, List, Type
from .base import BaseApp


class AppRegistry:
    """
    Registry central de apps.

    Gerencia o registro e acesso a todos os apps disponíveis.
    """

    _apps: Dict[str, BaseApp] = {}
    _initialized: bool = False

    @classmethod
    def _ensure_initialized(cls):
        """Garante que os apps estão registrados."""
        if not cls._initialized:
            cls._register_all_apps()
            cls._initialized = True

    @classmethod
    def _register_all_apps(cls):
        """Registra todos os apps disponíveis."""
        # Import e registro de cada app
        from .hubspot import hubspot_app
        from .clicksign import clicksign_app
        from .zapsign import zapsign_app
        from .google_docs import google_docs_app
        from .google_slides import google_slides_app
        from .google_drive import google_drive_app
        from .google_forms import google_forms_app
        from .microsoft_word import microsoft_word_app
        from .microsoft_powerpoint import microsoft_powerpoint_app
        from .gmail import gmail_app
        from .outlook import outlook_app
        from .ai import ai_app
        from .stripe import stripe_app
        from .storage import storage_app

        apps = [
            hubspot_app,
            clicksign_app,
            zapsign_app,
            google_docs_app,
            google_slides_app,
            google_drive_app,
            google_forms_app,
            microsoft_word_app,
            microsoft_powerpoint_app,
            gmail_app,
            outlook_app,
            ai_app,
            stripe_app,
            storage_app,
        ]

        for app in apps:
            cls.register(app)

    @classmethod
    def register(cls, app: BaseApp):
        """
        Registra um app no registry.

        Args:
            app: Instância do app a registrar
        """
        cls._apps[app.key] = app

    @classmethod
    def get(cls, key: str) -> Optional[BaseApp]:
        """
        Obtém um app pelo seu key.

        Args:
            key: Key único do app (ex: 'hubspot')

        Returns:
            App instance ou None se não encontrado
        """
        cls._ensure_initialized()
        return cls._apps.get(key)

    @classmethod
    def list_all(cls) -> List[BaseApp]:
        """
        Lista todos os apps registrados.

        Returns:
            Lista de instâncias de apps
        """
        cls._ensure_initialized()
        return list(cls._apps.values())

    @classmethod
    def list_keys(cls) -> List[str]:
        """
        Lista os keys de todos os apps.

        Returns:
            Lista de keys
        """
        cls._ensure_initialized()
        return list(cls._apps.keys())

    @classmethod
    def get_by_node_type(cls, node_type: str) -> Optional[BaseApp]:
        """
        Obtém um app pelo tipo de node.

        Mapeia tipos de node para apps:
        - 'google-docs' -> google_docs_app
        - 'hubspot' -> hubspot_app
        - etc.

        Args:
            node_type: Tipo do node de workflow

        Returns:
            App instance ou None
        """
        cls._ensure_initialized()

        # Mapeamento de node types para app keys
        node_type_map = {
            # Triggers
            'hubspot': 'hubspot',
            'google-forms': 'google-forms',
            # Document generation
            'google-docs': 'google-docs',
            'google-slides': 'google-slides',
            'microsoft-word': 'microsoft-word',
            'microsoft-powerpoint': 'microsoft-powerpoint',
            # Email
            'gmail': 'gmail',
            'outlook': 'outlook',
            # Signature
            'clicksign': 'clicksign',
            'request-signatures': 'clicksign',  # Default to clicksign
            'zapsign': 'zapsign',
            # Storage
            'file-upload': 'storage',
            'uploaded-document': 'storage',
        }

        app_key = node_type_map.get(node_type, node_type)
        return cls.get(app_key)

    @classmethod
    def to_dict(cls) -> Dict[str, dict]:
        """
        Converte todos os apps para dicionário.

        Returns:
            Dict com key -> app.to_dict()
        """
        cls._ensure_initialized()
        return {key: app.to_dict() for key, app in cls._apps.items()}


# Função helper para obter app
def get_app(key: str) -> Optional[BaseApp]:
    """
    Atalho para AppRegistry.get().

    Args:
        key: Key do app

    Returns:
        App instance ou None
    """
    return AppRegistry.get(key)


# Exportar classes e funções
__all__ = [
    'AppRegistry',
    'BaseApp',
    'get_app',
]
