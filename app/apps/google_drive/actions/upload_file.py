"""
Upload File Action.
"""

from typing import Dict, Any
import httpx


async def run(http_client: httpx.AsyncClient, parameters: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    file_content = parameters.get('file_content')
    file_name = parameters.get('file_name', 'file')
    folder_id = parameters.get('folder_id')
    mime_type = parameters.get('mime_type', 'application/octet-stream')

    if not file_content:
        raise ValueError("file_content is required")

    metadata = {'name': file_name, 'mimeType': mime_type}
    if folder_id:
        metadata['parents'] = [folder_id]

    # Simple upload for small files
    response = await http_client.post(
        'https://www.googleapis.com/upload/drive/v3/files?uploadType=media',
        content=file_content,
        headers={'Content-Type': mime_type}
    )
    response.raise_for_status()

    data = response.json()

    return {
        'file_id': data.get('id'),
        'name': data.get('name'),
        'url': f"https://drive.google.com/file/d/{data.get('id')}/view",
    }
