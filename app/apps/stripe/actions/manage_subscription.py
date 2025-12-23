"""Manage Subscription Action - Stripe."""

from typing import Dict, Any
import httpx


async def run(http_client: httpx.AsyncClient, parameters: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    subscription_id = parameters.get('subscription_id')
    action = parameters.get('action', 'get')

    if not subscription_id:
        raise ValueError("subscription_id is required")

    if action == 'cancel':
        response = await http_client.delete(f'/subscriptions/{subscription_id}')
    else:
        response = await http_client.get(f'/subscriptions/{subscription_id}')

    response.raise_for_status()
    data = response.json()

    return {'subscription_id': data.get('id'), 'status': data.get('status')}
