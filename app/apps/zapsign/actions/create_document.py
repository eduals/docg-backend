"""
Create Document Action - Cria documento para assinatura no ZapSign.
"""

from typing import Dict, Any
import httpx


async def run(
    http_client: httpx.AsyncClient,
    parameters: Dict[str, Any],
    context: Any = None,
) -> Dict[str, Any]:
    """
    Cria um documento para assinatura.

    Args:
        http_client: Cliente HTTP configurado
        parameters: {
            'name': 'document name',
            'url_pdf': 'url do PDF',
            'signers': [{'name': 'Name', 'email': 'email@example.com'}]
        }
        context: GlobalVariable context

    Returns:
        Dict com dados do documento criado
    """
    name = parameters.get('name', 'Document')
    url_pdf = parameters.get('url_pdf')
    signers = parameters.get('signers', [])

    if not url_pdf:
        raise ValueError("url_pdf is required")

    signer_list = []
    for signer in signers:
        signer_list.append({
            'name': signer.get('name', ''),
            'email': signer.get('email', ''),
        })

    response = await http_client.post(
        '/docs',
        json={
            'name': name,
            'url_pdf': url_pdf,
            'signers': signer_list,
        }
    )
    response.raise_for_status()

    data = response.json()

    return {
        'document_id': data.get('token'),
        'name': data.get('name'),
        'status': data.get('status'),
        'signers': data.get('signers', []),
    }
