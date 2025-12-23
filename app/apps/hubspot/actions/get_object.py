"""
Get Object Action - Busca dados de um objeto HubSpot.

Esta action busca dados de contacts, deals, companies ou tickets
do HubSpot usando o serviço de DataSource existente.
"""

from typing import Dict, Any
import httpx


async def run(
    http_client: httpx.AsyncClient,
    parameters: Dict[str, Any],
    context: Any = None,
) -> Dict[str, Any]:
    """
    Busca dados de um objeto HubSpot.

    Args:
        http_client: Cliente HTTP configurado com auth
        parameters: {
            'object_type': 'contact' | 'deal' | 'company' | 'ticket',
            'object_id': 'string',
            'properties': ['prop1', 'prop2'] (optional)
        }
        context: GlobalVariable context

    Returns:
        Dict com dados do objeto
    """
    object_type = parameters.get('object_type', 'contact')
    object_id = parameters.get('object_id')
    properties = parameters.get('properties', [])

    if not object_id:
        raise ValueError("object_id is required")

    # Normalizar tipo de objeto
    type_map = {
        'contact': 'contacts',
        'contacts': 'contacts',
        'deal': 'deals',
        'deals': 'deals',
        'company': 'companies',
        'companies': 'companies',
        'ticket': 'tickets',
        'tickets': 'tickets',
    }
    api_type = type_map.get(object_type.lower(), 'contacts')

    # Construir URL
    url = f"/crm/v3/objects/{api_type}/{object_id}"

    # Parâmetros
    params = {}
    if properties:
        params['properties'] = ','.join(properties)

    # Fazer requisição
    response = await http_client.get(url, params=params)
    response.raise_for_status()

    data = response.json()

    return {
        'id': data.get('id'),
        'properties': data.get('properties', {}),
        'associations': data.get('associations', {}),
        'created_at': data.get('createdAt'),
        'updated_at': data.get('updatedAt'),
    }
