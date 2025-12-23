"""
Updated Deal Trigger - Processa eventos de deal atualizado no HubSpot.
"""

from typing import Dict, Any
import httpx


async def run(
    http_client: httpx.AsyncClient,
    trigger_data: Dict[str, Any],
    context: Any = None,
) -> Dict[str, Any]:
    """
    Processa trigger de deal atualizado.

    Args:
        http_client: Cliente HTTP configurado
        trigger_data: Dados do webhook HubSpot
        context: GlobalVariable context

    Returns:
        Dict com dados do deal normalizado
    """
    deal_id = None

    if 'objectId' in trigger_data:
        deal_id = str(trigger_data['objectId'])
    elif 'dealId' in trigger_data:
        deal_id = str(trigger_data['dealId'])

    if not deal_id:
        return {
            'deal': trigger_data,
            'source': 'webhook',
        }

    try:
        response = await http_client.get(
            f'/crm/v3/objects/deals/{deal_id}',
            params={'properties': '*'}
        )
        response.raise_for_status()
        deal_data = response.json()

        return {
            'deal': {
                'id': deal_data.get('id'),
                'properties': deal_data.get('properties', {}),
                'created_at': deal_data.get('createdAt'),
                'updated_at': deal_data.get('updatedAt'),
            },
            'source': 'hubspot',
            'event_type': 'deal.updated',
            'changed_properties': trigger_data.get('propertyName'),
        }
    except Exception as e:
        return {
            'deal': trigger_data,
            'source': 'webhook',
            'error': str(e),
        }
