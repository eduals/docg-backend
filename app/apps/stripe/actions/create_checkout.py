"""Create Checkout Action - Stripe."""

from typing import Dict, Any
import httpx


async def run(http_client: httpx.AsyncClient, parameters: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    price_id = parameters.get('price_id')
    success_url = parameters.get('success_url')
    cancel_url = parameters.get('cancel_url')

    if not price_id:
        raise ValueError("price_id is required")

    response = await http_client.post(
        '/checkout/sessions',
        data={
            'mode': 'subscription',
            'line_items[0][price]': price_id,
            'line_items[0][quantity]': '1',
            'success_url': success_url or 'https://example.com/success',
            'cancel_url': cancel_url or 'https://example.com/cancel',
        }
    )
    response.raise_for_status()
    data = response.json()

    return {'session_id': data.get('id'), 'url': data.get('url')}
