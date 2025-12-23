"""
Create Ticket Action - Cria um novo ticket no HubSpot.

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
    Cria um novo ticket no HubSpot.

    Args:
        http_client: Cliente HTTP configurado com auth
        parameters: {
            'subject': 'Título do ticket',
            'content': 'Descrição do ticket' (optional),
            'priority': 'LOW' | 'MEDIUM' | 'HIGH' (optional),
            'pipeline': 'ID do pipeline' (optional),
            'pipeline_stage': 'ID do estágio' (optional),
            'properties': {...} (optional - propriedades adicionais)
        }
        context: GlobalVariable context

    Returns:
        Dict com dados do ticket criado
    """
    subject = parameters.get('subject')
    content = parameters.get('content', '')
    priority = parameters.get('priority', 'MEDIUM')
    pipeline = parameters.get('pipeline')
    pipeline_stage = parameters.get('pipeline_stage')
    extra_properties = parameters.get('properties', {})

    if not subject:
        raise ValueError("subject is required")

    # Construir propriedades do ticket
    properties = {
        'subject': subject,
        'content': content,
        'hs_ticket_priority': priority,
        **extra_properties
    }

    # Adicionar pipeline/estágio se fornecidos
    if pipeline:
        properties['hs_pipeline'] = pipeline
    if pipeline_stage:
        properties['hs_pipeline_stage'] = pipeline_stage

    # Criar ticket
    response = await http_client.post(
        '/crm/v3/objects/tickets',
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
