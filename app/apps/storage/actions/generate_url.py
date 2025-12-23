"""Generate URL Action - Storage."""

from typing import Dict, Any
import httpx


async def run(http_client: httpx.AsyncClient, parameters: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    from app.services.storage.digitalocean_spaces import DigitalOceanSpacesService

    file_key = parameters.get('file_key')
    expires_in = parameters.get('expires_in', 3600)

    if not file_key:
        raise ValueError("file_key is required")

    service = DigitalOceanSpacesService()
    url = service.generate_signed_url(file_key=file_key, expires_in=expires_in)

    return {'file_key': file_key, 'url': url, 'expires_in': expires_in}
