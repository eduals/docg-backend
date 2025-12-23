"""
Documents Controllers.

Controllers para gerenciamento de documentos gerados.
"""

from .list import list_documents
from .get import get_document
from .generate import generate_document
from .regenerate import regenerate_document
from .delete import delete_document
from .helpers import doc_to_dict

__all__ = [
    'list_documents',
    'get_document',
    'generate_document',
    'regenerate_document',
    'delete_document',
    'doc_to_dict',
]
