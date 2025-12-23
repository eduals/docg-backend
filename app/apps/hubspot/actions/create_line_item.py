"""
Create Line Item Action - Cria um line item e associa a um deal no HubSpot.

NOTA IMPORTANTE: O scope OAuth correto é 'e-commerce' (NÃO 'crm.objects.line_items').
"""

from typing import Dict, Any, Optional
import httpx


async def run(
    http_client: httpx.AsyncClient,
    parameters: Dict[str, Any],
    context: Any = None,
) -> Dict[str, Any]:
    """
    Cria um line item e opcionalmente associa a um deal.

    Args:
        http_client: Cliente HTTP configurado com auth
        parameters: {
            'deal_id': 'ID do deal para associar' (optional),
            'name': 'Nome do item',
            'price': 100.00,
            'quantity': 1 (optional, default 1),
            'discount': 0 (optional),
            'sku': 'SKU do item' (optional),
            'description': 'Descrição' (optional),
            'product_id': 'ID do produto' (optional),
            'properties': {...} (optional - propriedades adicionais)
        }
        context: GlobalVariable context

    Returns:
        Dict com dados do line item criado
    """
    deal_id = parameters.get('deal_id')
    name = parameters.get('name')
    price = parameters.get('price')
    quantity = parameters.get('quantity', 1)
    discount = parameters.get('discount', 0)
    sku = parameters.get('sku')
    description = parameters.get('description')
    product_id = parameters.get('product_id')
    extra_properties = parameters.get('properties', {})

    if not name:
        raise ValueError("name is required")
    if price is None:
        raise ValueError("price is required")

    # Construir propriedades do line item
    properties = {
        'name': name,
        'price': str(price),
        'quantity': str(quantity),
        **extra_properties
    }

    if discount:
        properties['discount'] = str(discount)
    if sku:
        properties['hs_sku'] = sku
    if description:
        properties['description'] = description
    if product_id:
        properties['hs_product_id'] = product_id

    # Calcular amount
    amount = (float(price) * float(quantity)) - float(discount or 0)
    properties['amount'] = str(amount)

    # Se temos deal_id, criar com associação
    if deal_id:
        body = {
            'properties': properties,
            'associations': [
                {
                    'to': {'id': deal_id},
                    'types': [
                        {
                            'associationCategory': 'HUBSPOT_DEFINED',
                            'associationTypeId': 19  # line_item_to_deal
                        }
                    ]
                }
            ]
        }
    else:
        body = {'properties': properties}

    # Criar line item
    response = await http_client.post(
        '/crm/v3/objects/line_items',
        json=body
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
        'deal_id': deal_id,
        'properties': props,
        'created_at': data.get('createdAt'),
        'updated_at': data.get('updatedAt'),
    }


async def associate_to_deal(
    http_client: httpx.AsyncClient,
    line_item_id: str,
    deal_id: str,
) -> Dict[str, Any]:
    """
    Associa um line item existente a um deal.

    Args:
        http_client: Cliente HTTP configurado
        line_item_id: ID do line item
        deal_id: ID do deal

    Returns:
        Dict confirmando a associação
    """
    response = await http_client.put(
        f'/crm/v4/objects/line_items/{line_item_id}/associations/deals/{deal_id}',
        json=[
            {
                'associationCategory': 'HUBSPOT_DEFINED',
                'associationTypeId': 19  # line_item_to_deal
            }
        ]
    )
    response.raise_for_status()

    return {
        'line_item_id': line_item_id,
        'deal_id': deal_id,
        'status': 'associated'
    }


def _parse_float(value) -> Optional[float]:
    """Parse string para float, retornando None se inválido."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None
