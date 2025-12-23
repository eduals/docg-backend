"""
Add Signer Action - Adiciona um signatário a um envelope.
"""

from typing import Dict, Any
import httpx


async def run(
    http_client: httpx.AsyncClient,
    parameters: Dict[str, Any],
    context: Any = None,
) -> Dict[str, Any]:
    """
    Adiciona um signatário ao envelope.

    Args:
        http_client: Cliente HTTP configurado
        parameters: {
            'envelope_id': 'document key',
            'email': 'signer email',
            'name': 'signer name',
            'phone': 'phone number' (optional),
            'auth_type': 'email' | 'sms' (optional)
        }
        context: GlobalVariable context

    Returns:
        Dict com dados do signatário
    """
    envelope_id = parameters.get('envelope_id')
    email = parameters.get('email')
    name = parameters.get('name')
    phone = parameters.get('phone')
    auth_type = parameters.get('auth_type', 'email')

    if not envelope_id:
        raise ValueError("envelope_id is required")
    if not email:
        raise ValueError("email is required")
    if not name:
        raise ValueError("name is required")

    # Criar signatário
    signer_data = {
        'signer': {
            'email': email,
            'name': name,
            'auths': [auth_type],
        }
    }

    if phone:
        signer_data['signer']['phone_number'] = phone

    response = await http_client.post('/signers', json=signer_data)
    response.raise_for_status()

    signer = response.json().get('signer', {})
    signer_key = signer.get('key')

    # Associar signatário ao documento
    list_response = await http_client.post(
        '/lists',
        json={
            'list': {
                'document_key': envelope_id,
                'signer_key': signer_key,
                'sign_as': 'sign',
            }
        }
    )
    list_response.raise_for_status()

    return {
        'signer_id': signer_key,
        'email': email,
        'name': name,
        'status': 'added',
    }
