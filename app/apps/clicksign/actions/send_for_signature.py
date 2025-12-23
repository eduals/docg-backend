"""
Send for Signature Action - Envia envelope para assinatura.
"""

from typing import Dict, Any
import httpx


async def run(
    http_client: httpx.AsyncClient,
    parameters: Dict[str, Any],
    context: Any = None,
) -> Dict[str, Any]:
    """
    Envia envelope para assinatura.

    Args:
        http_client: Cliente HTTP configurado
        parameters: {
            'envelope_id': 'document key',
            'message': 'mensagem opcional'
        }
        context: GlobalVariable context

    Returns:
        Dict com status do envio
    """
    envelope_id = parameters.get('envelope_id')
    message = parameters.get('message', '')

    if not envelope_id:
        raise ValueError("envelope_id is required")

    # Enviar notificações
    response = await http_client.post(
        f'/documents/{envelope_id}/notifications',
        json={
            'message': message,
        }
    )
    response.raise_for_status()

    return {
        'envelope_id': envelope_id,
        'status': 'sent',
        'message': message,
    }
