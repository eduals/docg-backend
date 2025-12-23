"""
Get Line Items Action - Busca line items de um deal no HubSpot.

NOTA IMPORTANTE: O scope OAuth correto é 'e-commerce' (NÃO 'crm.objects.line_items').
"""

from typing import Dict, Any, List
import httpx


async def run(
    http_client: httpx.AsyncClient,
    parameters: Dict[str, Any],
    context: Any = None,
) -> Dict[str, Any]:
    """
    Busca line items associados a um deal no HubSpot.

    Args:
        http_client: Cliente HTTP configurado com auth
        parameters: {
            'deal_id': 'ID do deal',
            'properties': ['name', 'price', 'quantity'] (optional)
        }
        context: GlobalVariable context

    Returns:
        Dict com lista de line items
    """
    deal_id = parameters.get('deal_id')
    properties = parameters.get('properties', [
        'name', 'price', 'quantity', 'amount', 'hs_sku',
        'discount', 'description', 'hs_product_id'
    ])

    if not deal_id:
        raise ValueError("deal_id is required")

    # Buscar associações de line items do deal
    assoc_response = await http_client.get(
        f'/crm/v4/objects/deals/{deal_id}/associations/line_items'
    )
    assoc_response.raise_for_status()

    associations = assoc_response.json().get('results', [])

    if not associations:
        return {
            'deal_id': deal_id,
            'line_items': [],
            'count': 0,
            'total_amount': 0
        }

    # Buscar detalhes de cada line item
    line_item_ids = [assoc.get('toObjectId') for assoc in associations]
    line_items = []
    total_amount = 0

    for li_id in line_item_ids:
        params = {}
        if properties:
            params['properties'] = ','.join(properties)

        response = await http_client.get(
            f'/crm/v3/objects/line_items/{li_id}',
            params=params
        )

        if response.status_code == 200:
            data = response.json()
            props = data.get('properties', {})

            # Parse valores numéricos
            price = _parse_float(props.get('price'))
            quantity = _parse_float(props.get('quantity', 1))
            discount = _parse_float(props.get('discount', 0))
            amount = _parse_float(props.get('amount'))

            # Calcular amount se não disponível
            if amount is None and price is not None:
                amount = (price * quantity) - discount

            if amount:
                total_amount += amount

            line_items.append({
                'id': data.get('id'),
                'name': props.get('name'),
                'description': props.get('description'),
                'sku': props.get('hs_sku'),
                'price': price,
                'quantity': quantity,
                'discount': discount,
                'amount': amount,
                'product_id': props.get('hs_product_id'),
                'properties': props,
                'created_at': data.get('createdAt'),
                'updated_at': data.get('updatedAt'),
            })

    return {
        'deal_id': deal_id,
        'line_items': line_items,
        'count': len(line_items),
        'total_amount': total_amount
    }


async def get_line_item(
    http_client: httpx.AsyncClient,
    line_item_id: str,
    properties: List[str] = None,
) -> Dict[str, Any]:
    """
    Busca um line item específico.

    Args:
        http_client: Cliente HTTP configurado
        line_item_id: ID do line item
        properties: Lista de propriedades a retornar

    Returns:
        Dict com dados do line item
    """
    params = {}
    if properties:
        params['properties'] = ','.join(properties)

    response = await http_client.get(
        f'/crm/v3/objects/line_items/{line_item_id}',
        params=params
    )
    response.raise_for_status()

    data = response.json()
    props = data.get('properties', {})

    return {
        'id': data.get('id'),
        'name': props.get('name'),
        'description': props.get('description'),
        'sku': props.get('hs_sku'),
        'price': _parse_float(props.get('price')),
        'quantity': _parse_float(props.get('quantity', 1)),
        'discount': _parse_float(props.get('discount', 0)),
        'amount': _parse_float(props.get('amount')),
        'product_id': props.get('hs_product_id'),
        'properties': props,
        'created_at': data.get('createdAt'),
        'updated_at': data.get('updatedAt'),
    }


def _parse_float(value) -> float:
    """Parse string para float, retornando None se inválido."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None
