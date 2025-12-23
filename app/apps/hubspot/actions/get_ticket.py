"""
Get Ticket Action - Busca dados de um ticket no HubSpot.

NOTA IMPORTANTE: O scope OAuth correto é 'tickets' (NÃO 'crm.objects.tickets').
"""

from typing import Dict, Any, List
import httpx


async def run(
    http_client: httpx.AsyncClient,
    parameters: Dict[str, Any],
    context: Any = None,
) -> Dict[str, Any]:
    """
    Busca dados de um ticket no HubSpot.

    Args:
        http_client: Cliente HTTP configurado com auth
        parameters: {
            'ticket_id': 'ID do ticket',
            'properties': ['prop1', 'prop2'] (optional),
            'include_associations': True | False (optional)
        }
        context: GlobalVariable context

    Returns:
        Dict com dados do ticket
    """
    ticket_id = parameters.get('ticket_id')
    properties = parameters.get('properties', [])
    include_associations = parameters.get('include_associations', False)

    if not ticket_id:
        raise ValueError("ticket_id is required")

    # Construir parâmetros
    params = {}
    if properties:
        params['properties'] = ','.join(properties)
    if include_associations:
        params['associations'] = 'contacts,companies'

    # Buscar ticket
    response = await http_client.get(
        f'/crm/v3/objects/tickets/{ticket_id}',
        params=params
    )
    response.raise_for_status()

    data = response.json()

    result = {
        'id': data.get('id'),
        'subject': data.get('properties', {}).get('subject'),
        'content': data.get('properties', {}).get('content'),
        'priority': data.get('properties', {}).get('hs_ticket_priority'),
        'status': data.get('properties', {}).get('hs_ticket_status'),
        'pipeline': data.get('properties', {}).get('hs_pipeline'),
        'pipeline_stage': data.get('properties', {}).get('hs_pipeline_stage'),
        'properties': data.get('properties', {}),
        'created_at': data.get('createdAt'),
        'updated_at': data.get('updatedAt'),
    }

    # Incluir associações se solicitado
    if include_associations and 'associations' in data:
        result['associations'] = data.get('associations', {})

    return result


async def search_tickets(
    http_client: httpx.AsyncClient,
    query: str = None,
    filters: List[Dict] = None,
    properties: List[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """
    Busca tickets por query ou filtros.

    Args:
        http_client: Cliente HTTP configurado
        query: Texto de busca (opcional)
        filters: Lista de filtros (opcional)
        properties: Lista de propriedades a retornar (opcional)
        limit: Limite de resultados (max 100)

    Returns:
        Lista de tickets encontrados
    """
    body = {'limit': limit}

    if query:
        body['query'] = query
    if filters:
        body['filterGroups'] = [{'filters': filters}]
    if properties:
        body['properties'] = properties

    response = await http_client.post(
        '/crm/v3/objects/tickets/search',
        json=body
    )
    response.raise_for_status()

    results = response.json().get('results', [])

    return [
        {
            'id': item.get('id'),
            'subject': item.get('properties', {}).get('subject'),
            'priority': item.get('properties', {}).get('hs_ticket_priority'),
            'status': item.get('properties', {}).get('hs_ticket_status'),
            'properties': item.get('properties', {}),
        }
        for item in results
    ]
