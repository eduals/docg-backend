"""
New Contact Trigger - Processa eventos de novo contato no HubSpot.
"""

from typing import Dict, Any
import httpx


async def run(
    http_client: httpx.AsyncClient,
    trigger_data: Dict[str, Any],
    context: Any = None,
) -> Dict[str, Any]:
    """
    Processa trigger de novo contato.

    Args:
        http_client: Cliente HTTP configurado
        trigger_data: Dados do webhook HubSpot
        context: GlobalVariable context

    Returns:
        Dict com dados do contato normalizado
    """
    contact_id = None

    if 'objectId' in trigger_data:
        contact_id = str(trigger_data['objectId'])
    elif 'vid' in trigger_data:
        contact_id = str(trigger_data['vid'])
    elif 'properties' in trigger_data and 'hs_object_id' in trigger_data.get('properties', {}):
        contact_id = str(trigger_data['properties']['hs_object_id'])

    if not contact_id:
        return {
            'contact': trigger_data,
            'source': 'webhook',
        }

    try:
        response = await http_client.get(
            f'/crm/v3/objects/contacts/{contact_id}',
            params={'properties': '*'}
        )
        response.raise_for_status()
        contact_data = response.json()

        return {
            'contact': {
                'id': contact_data.get('id'),
                'properties': contact_data.get('properties', {}),
                'created_at': contact_data.get('createdAt'),
                'updated_at': contact_data.get('updatedAt'),
            },
            'source': 'hubspot',
            'event_type': 'contact.created',
        }
    except Exception as e:
        return {
            'contact': trigger_data,
            'source': 'webhook',
            'error': str(e),
        }
