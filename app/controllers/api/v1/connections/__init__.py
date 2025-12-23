"""
Connections Controllers.

Controllers para gerenciamento de conexões de dados, IA e assinatura.
"""

from .list import list_connections
from .get import get_connection
from .create import create_connection
from .update import update_connection
from .delete import delete_connection
from .test import test_connection

# AI Connections
from .ai import (
    list_ai_connections,
    get_ai_connection,
    create_ai_connection,
    update_ai_connection,
    delete_ai_connection,
    test_ai_connection,
)

# Signature Connections
from .signature import (
    list_signature_connections,
    get_signature_connection,
    create_signature_connection,
    update_signature_connection,
    delete_signature_connection,
    test_signature_connection,
)

__all__ = [
    # Base connections
    'list_connections',
    'get_connection',
    'create_connection',
    'update_connection',
    'delete_connection',
    'test_connection',
    # AI connections
    'list_ai_connections',
    'get_ai_connection',
    'create_ai_connection',
    'update_ai_connection',
    'delete_ai_connection',
    'test_ai_connection',
    # Signature connections
    'list_signature_connections',
    'get_signature_connection',
    'create_signature_connection',
    'update_signature_connection',
    'delete_signature_connection',
    'test_signature_connection',
]
