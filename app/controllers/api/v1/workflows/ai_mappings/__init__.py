"""
AI Mappings Controllers.
"""

from .list import list_ai_mappings
from .get import get_ai_mapping
from .create import create_ai_mapping
from .update import update_ai_mapping
from .delete import delete_ai_mapping

__all__ = [
    'list_ai_mappings',
    'get_ai_mapping',
    'create_ai_mapping',
    'update_ai_mapping',
    'delete_ai_mapping',
]
