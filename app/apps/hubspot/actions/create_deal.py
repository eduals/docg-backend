"""
Create Deal Action - Cria um novo deal no HubSpot.
"""

from typing import Dict, Any
import httpx


async def run(
    http_client: httpx.AsyncClient,
    parameters: Dict[str, Any],
    context: Any = None,
) -> Dict[str, Any]:
    """
    Cria um novo deal no HubSpot.

    Args:
        http_client: Cliente HTTP configurado
        parameters: {
            'dealname': 'Deal Name' (required),
            'amount': 1000,
            'dealstage': 'stage_id',
            'pipeline': 'pipeline_id',
            'properties': {'custom_prop': 'value'}
        }
        context: GlobalVariable context

    Returns:
        Dict com dados do deal criado
    """
    dealname = parameters.get('dealname')
    if not dealname:
        raise ValueError("dealname is required")

    properties = {
        'dealname': dealname,
    }

    if parameters.get('amount'):
        properties['amount'] = str(parameters['amount'])
    if parameters.get('dealstage'):
        properties['dealstage'] = parameters['dealstage']
    if parameters.get('pipeline'):
        properties['pipeline'] = parameters['pipeline']

    extra_props = parameters.get('properties', {})
    properties.update(extra_props)

    response = await http_client.post(
        '/crm/v3/objects/deals',
        json={'properties': properties}
    )
    response.raise_for_status()

    data = response.json()

    return {
        'id': data.get('id'),
        'properties': data.get('properties', {}),
        'created_at': data.get('createdAt'),
    }
