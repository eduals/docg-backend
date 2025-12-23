"""
Update Ticket Action - Atualiza um ticket existente no HubSpot.

NOTA IMPORTANTE: O scope OAuth correto é 'tickets' (NÃO 'crm.objects.tickets').
"""

from typing import Dict, Any
import httpx


async def run(
    http_client: httpx.AsyncClient,
    parameters: Dict[str, Any],
    context: Any = None,
) -> Dict[str, Any]:
    """
    Atualiza um ticket existente no HubSpot.

    Args:
        http_client: Cliente HTTP configurado com auth
        parameters: {
            'ticket_id': 'ID do ticket',
            'subject': 'Novo título' (optional),
            'content': 'Nova descrição' (optional),
            'priority': 'LOW' | 'MEDIUM' | 'HIGH' (optional),
            'status': 'Novo status' (optional),
            'pipeline_stage': 'ID do estágio' (optional),
            'properties': {...} (optional - propriedades adicionais)
        }
        context: GlobalVariable context

    Returns:
        Dict com dados do ticket atualizado
    """
    ticket_id = parameters.get('ticket_id')
    extra_properties = parameters.get('properties', {})

    if not ticket_id:
        raise ValueError("ticket_id is required")

    # Construir propriedades a atualizar
    properties = {**extra_properties}

    # Adicionar campos específicos se fornecidos
    if 'subject' in parameters:
        properties['subject'] = parameters['subject']
    if 'content' in parameters:
        properties['content'] = parameters['content']
    if 'priority' in parameters:
        properties['hs_ticket_priority'] = parameters['priority']
    if 'status' in parameters:
        properties['hs_ticket_status'] = parameters['status']
    if 'pipeline_stage' in parameters:
        properties['hs_pipeline_stage'] = parameters['pipeline_stage']

    if not properties:
        raise ValueError("At least one property to update is required")

    # Atualizar ticket
    response = await http_client.patch(
        f'/crm/v3/objects/tickets/{ticket_id}',
        json={'properties': properties}
    )
    response.raise_for_status()

    data = response.json()

    return {
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
