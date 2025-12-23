"""
List Properties - Lista propriedades de um tipo de objeto HubSpot.
"""

from typing import Dict, Any, List
import httpx


async def run(
    http_client: httpx.AsyncClient,
    params: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Lista todas as propriedades de um tipo de objeto.

    Args:
        http_client: Cliente HTTP configurado
        params: {'object_type': 'contact' | 'deal' | 'company'}

    Returns:
        Lista de [{'label': 'Property Name', 'value': 'property_key'}, ...]
    """
    object_type = params.get('object_type', 'contact')

    # Mapear para endpoint correto
    type_map = {
        'contact': 'contacts',
        'deal': 'deals',
        'company': 'companies',
        'ticket': 'tickets',
    }
    api_type = type_map.get(object_type.lower(), 'contacts')

    response = await http_client.get(f'/crm/v3/properties/{api_type}')
    response.raise_for_status()

    data = response.json()
    results = data.get('results', [])

    # Formatar para dropdown
    properties = []
    for prop in results:
        properties.append({
            'label': prop.get('label', prop.get('name')),
            'value': prop.get('name'),
            'description': prop.get('description', ''),
            'type': prop.get('type'),
            'field_type': prop.get('fieldType'),
        })

    # Ordenar por label
    properties.sort(key=lambda x: x['label'].lower())

    return properties
