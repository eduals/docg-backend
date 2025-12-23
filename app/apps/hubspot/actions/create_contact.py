"""
Create Contact Action - Cria um novo contato no HubSpot.
"""

from typing import Dict, Any
import httpx


async def run(
    http_client: httpx.AsyncClient,
    parameters: Dict[str, Any],
    context: Any = None,
) -> Dict[str, Any]:
    """
    Cria um novo contato no HubSpot.

    Args:
        http_client: Cliente HTTP configurado
        parameters: {
            'email': 'email@example.com' (required),
            'firstname': 'John',
            'lastname': 'Doe',
            'properties': {'custom_prop': 'value'}
        }
        context: GlobalVariable context

    Returns:
        Dict com dados do contato criado
    """
    email = parameters.get('email')
    if not email:
        raise ValueError("email is required")

    # Construir propriedades
    properties = {
        'email': email,
    }

    if parameters.get('firstname'):
        properties['firstname'] = parameters['firstname']
    if parameters.get('lastname'):
        properties['lastname'] = parameters['lastname']

    # Adicionar propriedades extras
    extra_props = parameters.get('properties', {})
    properties.update(extra_props)

    # Criar contato
    response = await http_client.post(
        '/crm/v3/objects/contacts',
        json={'properties': properties}
    )
    response.raise_for_status()

    data = response.json()

    return {
        'id': data.get('id'),
        'properties': data.get('properties', {}),
        'created_at': data.get('createdAt'),
    }
