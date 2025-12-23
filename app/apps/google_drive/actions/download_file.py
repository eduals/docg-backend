"""
Download File Action.
"""

from typing import Dict, Any
import httpx


async def run(http_client: httpx.AsyncClient, parameters: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    file_id = parameters.get('file_id')

    if not file_id:
        raise ValueError("file_id is required")

    response = await http_client.get(
        f'/files/{file_id}',
        params={'alt': 'media'}
    )
    response.raise_for_status()

    return {
        'file_id': file_id,
        'content': response.content,
        'size': len(response.content),
    }
