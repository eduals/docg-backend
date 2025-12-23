"""Upload File Action - Storage."""

from typing import Dict, Any
import httpx


async def run(http_client: httpx.AsyncClient, parameters: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    from app.services.storage.digitalocean_spaces import DigitalOceanSpacesService

    file_content = parameters.get('file_content')
    file_name = parameters.get('file_name')
    content_type = parameters.get('content_type', 'application/octet-stream')

    if not file_content or not file_name:
        raise ValueError("file_content and file_name are required")

    service = DigitalOceanSpacesService()
    result = service.upload_file(file_content=file_content, file_name=file_name, content_type=content_type)

    return {'file_key': result.get('key'), 'url': result.get('url')}
