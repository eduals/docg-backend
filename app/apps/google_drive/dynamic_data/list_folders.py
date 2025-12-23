"""
List Folders Dynamic Data.
"""

from typing import Dict, Any, List
import httpx


async def run(http_client: httpx.AsyncClient, params: Dict[str, Any]) -> List[Dict[str, Any]]:
    parent_id = params.get('parent_id', 'root')

    query = f"'{parent_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"

    response = await http_client.get(
        '/files',
        params={
            'q': query,
            'fields': 'files(id, name)',
            'orderBy': 'name',
        }
    )
    response.raise_for_status()

    data = response.json()

    return [
        {'label': f.get('name'), 'value': f.get('id')}
        for f in data.get('files', [])
    ]
