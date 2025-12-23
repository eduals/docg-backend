"""
Export PDF Action - Exporta apresentação Google Slides como PDF.
"""

from typing import Dict, Any
import httpx


async def run(
    http_client: httpx.AsyncClient,
    parameters: Dict[str, Any],
    context: Any = None,
) -> Dict[str, Any]:
    presentation_id = parameters.get('presentation_id')

    if not presentation_id:
        raise ValueError("presentation_id is required")

    drive_url = 'https://www.googleapis.com/drive/v3'

    response = await http_client.get(
        f'{drive_url}/files/{presentation_id}/export',
        params={'mimeType': 'application/pdf'}
    )
    response.raise_for_status()

    pdf_content = response.content

    return {
        'presentation_id': presentation_id,
        'pdf_size': len(pdf_content),
        'status': 'exported',
    }
