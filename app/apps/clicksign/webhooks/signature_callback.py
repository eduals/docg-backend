"""
Signature Callback - Processa webhooks de assinatura do ClickSign.
"""

from typing import Dict, Any


def process_webhook(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Processa webhook de assinatura do ClickSign.

    Args:
        payload: Payload do webhook

    Returns:
        Dict com dados normalizados
    """
    event = payload.get('event', {})
    document = payload.get('document', {})
    signer = payload.get('signer', {})

    event_name = event.get('name', '')

    # Mapear eventos para status
    status_map = {
        'sign': 'signed',
        'refuse': 'declined',
        'cancel': 'cancelled',
        'close': 'completed',
        'deadline': 'expired',
    }

    status = status_map.get(event_name, event_name)

    return {
        'event_type': event_name,
        'status': status,
        'document_key': document.get('key'),
        'signer_email': signer.get('email'),
        'signer_name': signer.get('name'),
        'signed_at': event.get('occurred_at'),
        'raw_payload': payload,
    }
