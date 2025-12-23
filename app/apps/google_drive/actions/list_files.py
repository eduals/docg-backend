"""
List Files Action.
"""

from typing import Dict, Any
import httpx


async def run(http_client: httpx.AsyncClient, parameters: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    folder_id = parameters.get('folder_id', 'root')
    page_size = parameters.get('page_size', 100)

    query = f"'{folder_id}' in parents and trashed = false"

    response = await http_client.get(
        '/files',
        params={
            'q': query,
            'pageSize': page_size,
            'fields': 'files(id, name, mimeType, size, createdTime)',
        }
    )
    response.raise_for_status()

    data = response.json()

    return {
        'files': data.get('files', []),
        'count': len(data.get('files', [])),
    }
