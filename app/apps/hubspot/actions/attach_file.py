"""
Attach File Action - Anexa um arquivo a um objeto HubSpot.

Esta action usa o HubSpotAttachmentService existente para
fazer upload e anexar arquivos a objetos do CRM.
"""

from typing import Dict, Any
import httpx


async def run(
    http_client: httpx.AsyncClient,
    parameters: Dict[str, Any],
    context: Any = None,
) -> Dict[str, Any]:
    """
    Anexa um arquivo a um objeto HubSpot.

    Args:
        http_client: Cliente HTTP configurado
        parameters: {
            'object_type': 'contact' | 'deal' | 'company',
            'object_id': 'string',
            'file_url': 'url do arquivo',
            'file_name': 'nome do arquivo',
            'folder_path': 'caminho no HubSpot (optional)'
        }
        context: GlobalVariable context

    Returns:
        Dict com informações do arquivo anexado
    """
    # Import do serviço existente
    from app.services.data_sources.hubspot_attachments import HubSpotAttachmentService
    from app.models import DataSourceConnection

    object_type = parameters.get('object_type', 'contact')
    object_id = parameters.get('object_id')
    file_url = parameters.get('file_url')
    file_name = parameters.get('file_name', 'attachment.pdf')
    folder_path = parameters.get('folder_path', '/docg')

    if not object_id:
        raise ValueError("object_id is required")
    if not file_url:
        raise ValueError("file_url is required")

    # Obter connection_id do context se disponível
    connection_id = None
    if context and hasattr(context, 'auth') and context.auth:
        connection_id = context.auth.connection_id

    if not connection_id:
        raise ValueError("connection_id is required in context")

    connection = DataSourceConnection.query.get(connection_id)
    if not connection:
        raise ValueError(f"Connection {connection_id} not found")

    # Usar serviço existente
    service = HubSpotAttachmentService(connection)

    # Download do arquivo
    import httpx as httpx_sync
    async with httpx_sync.AsyncClient() as client:
        file_response = await client.get(file_url)
        file_content = file_response.content

    # Upload e anexar
    result = service.upload_and_attach(
        file_content=file_content,
        file_name=file_name,
        object_type=object_type,
        object_id=object_id,
        folder_path=folder_path,
    )

    return {
        'file_id': result.get('id'),
        'file_name': file_name,
        'object_type': object_type,
        'object_id': object_id,
        'attached': True,
    }
