"""
Replace Tags Action - Microsoft Word.

NOTE: Microsoft Graph doesn't support direct text replacement.
This uses the existing MicrosoftWordService.
"""

from typing import Dict, Any
import httpx


async def run(http_client: httpx.AsyncClient, parameters: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    document_id = parameters.get('document_id')
    replacements = parameters.get('replacements', {})

    if not document_id:
        raise ValueError("document_id is required")

    # Use existing service for complex operations
    from app.services.document_generation.microsoft_word import MicrosoftWordService
    from app.models import DataSourceConnection

    connection_id = None
    if context and hasattr(context, 'auth') and context.auth:
        connection_id = context.auth.connection_id

    if connection_id:
        connection = DataSourceConnection.query.get(connection_id)
        if connection:
            service = MicrosoftWordService(connection.get_credentials())
            result = service.replace_tags_in_document(document_id, replacements)
            return {
                'document_id': document_id,
                'replacements_count': len(replacements),
                'status': 'success',
            }

    return {
        'document_id': document_id,
        'status': 'error',
        'message': 'Connection not found',
    }
