"""
Signature Callback - Processa webhooks de assinatura do ZapSign.
"""

from typing import Dict, Any


def process_webhook(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Processa webhook de assinatura do ZapSign.

    Args:
        payload: Payload do webhook

    Returns:
        Dict com dados normalizados
    """
    status_map = {
        'signed': 'signed',
        'refused': 'declined',
        'cancelled': 'cancelled',
    }

    event_type = payload.get('event_type', '')
    status = status_map.get(event_type, event_type)

    return {
        'event_type': event_type,
        'status': status,
        'document_id': payload.get('document_token'),
        'signer_email': payload.get('signer', {}).get('email'),
        'signer_name': payload.get('signer', {}).get('name'),
        'signed_at': payload.get('signed_at'),
        'raw_payload': payload,
    }
