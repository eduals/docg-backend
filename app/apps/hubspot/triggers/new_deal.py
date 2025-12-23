"""
New Deal Trigger - Processa eventos de novo deal no HubSpot.
"""

from typing import Dict, Any
import httpx


async def run(
    http_client: httpx.AsyncClient,
    trigger_data: Dict[str, Any],
    context: Any = None,
) -> Dict[str, Any]:
    """
    Processa trigger de novo deal.

    Args:
        http_client: Cliente HTTP configurado
        trigger_data: Dados do webhook HubSpot
        context: GlobalVariable context

    Returns:
        Dict com dados do deal normalizado
    """
    # Extrair deal ID do webhook payload
    deal_id = None

    # HubSpot envia eventos em formato diferente
    if 'objectId' in trigger_data:
        deal_id = str(trigger_data['objectId'])
    elif 'dealId' in trigger_data:
        deal_id = str(trigger_data['dealId'])
    elif 'properties' in trigger_data and 'hs_object_id' in trigger_data.get('properties', {}):
        deal_id = str(trigger_data['properties']['hs_object_id'])

    if not deal_id:
        # Se não tem ID, retornar os dados como estão
        return {
            'deal': trigger_data,
            'source': 'webhook',
        }

    # Buscar dados completos do deal
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
            'event_type': 'deal.created',
        }
    except Exception as e:
        # Se falhar ao buscar, retorna dados do webhook
        return {
            'deal': trigger_data,
            'source': 'webhook',
            'error': str(e),
        }
