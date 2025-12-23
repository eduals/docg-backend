"""Export PDF Action - Microsoft PowerPoint."""

from typing import Dict, Any
import httpx


async def run(http_client: httpx.AsyncClient, parameters: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    presentation_id = parameters.get('presentation_id')

    if not presentation_id:
        raise ValueError("presentation_id is required")

    response = await http_client.get(f'/me/drive/items/{presentation_id}/content', params={'format': 'pdf'})
    response.raise_for_status()

    return {'presentation_id': presentation_id, 'pdf_size': len(response.content), 'status': 'exported'}
