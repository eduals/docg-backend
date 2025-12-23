"""
Document Helpers - Funções auxiliares para controllers de documentos.
"""

from app.models import GeneratedDocument


def doc_to_dict(doc: GeneratedDocument, include_details: bool = False) -> dict:
    """Converte documento para dicionário"""
    result = doc.to_dict(include_details=include_details)
    return result
