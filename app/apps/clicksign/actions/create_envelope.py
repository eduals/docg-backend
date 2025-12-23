"""
Create Envelope Action - Cria um envelope de assinatura no ClickSign.
"""

from typing import Dict, Any
import httpx


async def run(
    http_client: httpx.AsyncClient,
    parameters: Dict[str, Any],
    context: Any = None,
) -> Dict[str, Any]:
    """
    Cria um novo envelope de assinatura.

    Args:
        http_client: Cliente HTTP configurado
        parameters: {
            'document_url': 'url do documento PDF',
            'document_name': 'nome do documento' (optional),
            'folder_path': 'caminho no ClickSign' (optional)
        }
        context: GlobalVariable context

    Returns:
        Dict com dados do envelope criado
    """
    document_url = parameters.get('document_url')
    document_name = parameters.get('document_name', 'document.pdf')
    folder_path = parameters.get('folder_path', '/')

    if not document_url:
        raise ValueError("document_url is required")

    # Download do documento
    async with httpx.AsyncClient() as download_client:
        doc_response = await download_client.get(document_url)
        doc_response.raise_for_status()
        document_content = doc_response.content

    # Upload para ClickSign
    import base64
    doc_base64 = base64.b64encode(document_content).decode('utf-8')

    response = await http_client.post(
        '/documents',
        json={
            'document': {
                'path': f'{folder_path}/{document_name}',
                'content_base64': f'data:application/pdf;base64,{doc_base64}',
            }
        }
    )
    response.raise_for_status()

    data = response.json()
    document = data.get('document', {})

    return {
        'envelope_id': document.get('key'),
        'document_key': document.get('key'),
        'status': document.get('status'),
        'created_at': document.get('created_at'),
    }
