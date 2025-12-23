"""
Copy Template Action - Cria cópia de um template Google Docs.
"""

from typing import Dict, Any
import httpx


async def run(
    http_client: httpx.AsyncClient,
    parameters: Dict[str, Any],
    context: Any = None,
) -> Dict[str, Any]:
    """
    Cria uma cópia de um template Google Docs.

    Args:
        http_client: Cliente HTTP configurado
        parameters: {
            'template_id': 'ID do template',
            'name': 'nome do novo documento',
            'folder_id': 'ID da pasta destino' (optional)
        }
        context: GlobalVariable context

    Returns:
        Dict com dados do documento criado
    """
    template_id = parameters.get('template_id')
    name = parameters.get('name', 'Document Copy')
    folder_id = parameters.get('folder_id')

    if not template_id:
        raise ValueError("template_id is required")

    # Usar Drive API para copiar
    drive_url = 'https://www.googleapis.com/drive/v3'

    body = {'name': name}
    if folder_id:
        body['parents'] = [folder_id]

    response = await http_client.post(
        f'{drive_url}/files/{template_id}/copy',
        json=body
    )
    response.raise_for_status()

    data = response.json()

    return {
        'document_id': data.get('id'),
        'name': data.get('name'),
        'url': f"https://docs.google.com/document/d/{data.get('id')}/edit",
    }
