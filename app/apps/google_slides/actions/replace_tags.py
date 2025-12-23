"""
Replace Tags Action - Substitui tags em apresentação Google Slides.
"""

from typing import Dict, Any, List
import httpx


async def run(
    http_client: httpx.AsyncClient,
    parameters: Dict[str, Any],
    context: Any = None,
) -> Dict[str, Any]:
    presentation_id = parameters.get('presentation_id')
    replacements = parameters.get('replacements', {})

    if not presentation_id:
        raise ValueError("presentation_id is required")

    requests: List[Dict] = []
    for tag, value in replacements.items():
        search_text = tag if '{{' in tag else f'{{{{{tag}}}}}'

        requests.append({
            'replaceAllText': {
                'containsText': {
                    'text': search_text,
                    'matchCase': False,
                },
                'replaceText': str(value) if value is not None else '',
            }
        })

    if requests:
        response = await http_client.post(
            f'https://slides.googleapis.com/v1/presentations/{presentation_id}:batchUpdate',
            json={'requests': requests}
        )
        response.raise_for_status()

    return {
        'presentation_id': presentation_id,
        'replacements_count': len(replacements),
        'status': 'success',
    }
