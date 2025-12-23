"""Download File Action - Storage."""

from typing import Dict, Any
import httpx


async def run(http_client: httpx.AsyncClient, parameters: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    from app.services.storage.digitalocean_spaces import DigitalOceanSpacesService

    file_key = parameters.get('file_key')

    if not file_key:
        raise ValueError("file_key is required")

    service = DigitalOceanSpacesService()
    content = service.download_file(file_key=file_key)

    return {'file_key': file_key, 'content': content, 'size': len(content) if content else 0}
