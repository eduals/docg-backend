"""Stripe Events Webhook Handler."""

from typing import Dict, Any


def process_webhook(payload: Dict[str, Any], signature: str = None) -> Dict[str, Any]:
    event_type = payload.get('type', '')
    data = payload.get('data', {}).get('object', {})

    return {
        'event_type': event_type,
        'object_id': data.get('id'),
        'customer_id': data.get('customer'),
        'status': data.get('status'),
        'raw_payload': payload,
    }
