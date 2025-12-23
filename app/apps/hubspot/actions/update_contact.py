"""
Update Contact Action - Atualiza um contato existente no HubSpot.
"""

from typing import Dict, Any
import httpx


async def run(
    http_client: httpx.AsyncClient,
    parameters: Dict[str, Any],
    context: Any = None,
) -> Dict[str, Any]:
    """
    Atualiza um contato existente no HubSpot.

    Args:
        http_client: Cliente HTTP configurado
        parameters: {
            'contact_id': 'id' (required),
            'properties': {'prop': 'value'}
        }
        context: GlobalVariable context

    Returns:
        Dict com dados do contato atualizado
    """
    contact_id = parameters.get('contact_id')
    if not contact_id:
        raise ValueError("contact_id is required")

    properties = parameters.get('properties', {})
    if not properties:
        raise ValueError("properties is required")

    response = await http_client.patch(
        f'/crm/v3/objects/contacts/{contact_id}',
        json={'properties': properties}
    )
    response.raise_for_status()

    data = response.json()

    return {
        'id': data.get('id'),
        'properties': data.get('properties', {}),
        'updated_at': data.get('updatedAt'),
    }
