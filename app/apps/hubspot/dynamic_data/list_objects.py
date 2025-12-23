"""
List Objects - Lista objetos de um tipo no HubSpot.
"""

from typing import Dict, Any, List
import httpx


async def run(
    http_client: httpx.AsyncClient,
    params: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Lista objetos de um tipo específico.

    Args:
        http_client: Cliente HTTP configurado
        params: {
            'object_type': 'contact' | 'deal' | 'company',
            'limit': 100 (optional),
            'search': 'search term' (optional)
        }

    Returns:
        Lista de [{'label': 'Object Name', 'value': 'object_id'}, ...]
    """
    object_type = params.get('object_type', 'contact')
    limit = params.get('limit', 100)
    search = params.get('search', '')

    type_map = {
        'contact': 'contacts',
        'deal': 'deals',
        'company': 'companies',
        'ticket': 'tickets',
    }
    api_type = type_map.get(object_type.lower(), 'contacts')

    # Label property por tipo
    label_props = {
        'contacts': ['email', 'firstname', 'lastname'],
        'deals': ['dealname'],
        'companies': ['name'],
        'tickets': ['subject'],
    }
    props = label_props.get(api_type, ['name'])

    if search:
        # Usar endpoint de search
        response = await http_client.post(
            f'/crm/v3/objects/{api_type}/search',
            json={
                'query': search,
                'limit': limit,
                'properties': props,
            }
        )
    else:
        response = await http_client.get(
            f'/crm/v3/objects/{api_type}',
            params={
                'limit': limit,
                'properties': ','.join(props),
            }
        )

    response.raise_for_status()
    data = response.json()
    results = data.get('results', [])

    objects = []
    for obj in results:
        props_data = obj.get('properties', {})

        # Construir label baseado no tipo
        if api_type == 'contacts':
            label = f"{props_data.get('firstname', '')} {props_data.get('lastname', '')}".strip()
            if not label:
                label = props_data.get('email', obj.get('id'))
        elif api_type == 'deals':
            label = props_data.get('dealname', obj.get('id'))
        elif api_type == 'companies':
            label = props_data.get('name', obj.get('id'))
        else:
            label = props_data.get('subject', obj.get('id'))

        objects.append({
            'label': label,
            'value': obj.get('id'),
        })

    return objects
