"""
Export PDF Action - Microsoft Word.
"""

from typing import Dict, Any
import httpx


async def run(http_client: httpx.AsyncClient, parameters: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    document_id = parameters.get('document_id')

    if not document_id:
        raise ValueError("document_id is required")

    response = await http_client.get(
        f'/me/drive/items/{document_id}/content',
        params={'format': 'pdf'}
    )
    response.raise_for_status()

    pdf_content = response.content

    return {
        'document_id': document_id,
        'pdf_size': len(pdf_content),
        'status': 'exported',
    }
