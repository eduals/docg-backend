"""
Templates Controllers.

Controllers para gerenciamento de templates de documentos.
"""

from .list import list_templates
from .get import get_template
from .create import create_template
from .update import update_template
from .delete import delete_template
from .upload import upload_template
from .sync import sync_template
from .tags import get_template_tags
from .open_editor import open_editor
from .available import list_available_templates
from .helpers import template_to_dict

# Alias para compatibilidade
sync_template_tags = sync_template

__all__ = [
    'list_templates',
    'get_template',
    'create_template',
    'update_template',
    'delete_template',
    'upload_template',
    'sync_template',
    'sync_template_tags',
    'get_template_tags',
    'open_editor',
    'list_available_templates',
    'template_to_dict',
]
