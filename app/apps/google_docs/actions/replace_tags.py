"""
Replace Tags Action - Substitui tags em documento Google Docs.
"""

from typing import Dict, Any, List
import httpx


async def run(
    http_client: httpx.AsyncClient,
    parameters: Dict[str, Any],
    context: Any = None,
) -> Dict[str, Any]:
    """
    Substitui {{tags}} em um documento.

    Args:
        http_client: Cliente HTTP configurado
        parameters: {
            'document_id': 'ID do documento',
            'replacements': {'tag': 'valor', ...}
        }
        context: GlobalVariable context

    Returns:
        Dict com status da substituição
    """
    document_id = parameters.get('document_id')
    replacements = parameters.get('replacements', {})

    if not document_id:
        raise ValueError("document_id is required")

    # Construir requests de substituição
    requests: List[Dict] = []
    for tag, value in replacements.items():
        # Suportar tags com ou sem {{ }}
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
            f'https://docs.googleapis.com/v1/documents/{document_id}:batchUpdate',
            json={'requests': requests}
        )
        response.raise_for_status()

    return {
        'document_id': document_id,
        'replacements_count': len(replacements),
        'status': 'success',
    }
