"""
HubSpot - Get Deal action
"""
import httpx
from app.pieces.base import ActionResult, ExecutionContext


async def get_deal_handler(props: dict, ctx: ExecutionContext) -> ActionResult:
    """
    Get a HubSpot deal by ID
    """
    deal_id = props.get('deal_id')

    if not deal_id:
        return ActionResult(
            success=False,
            error={"message": "deal_id is required"}
        )

    # Get access token from credentials
    credentials = ctx.credentials
    access_token = credentials.get('access_token')

    if not access_token:
        return ActionResult(
            success=False,
            error={"message": "No access token found in credentials"}
        )

    try:
        async with httpx.AsyncClient() as client:
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }

            url = f'https://api.hubapi.com/crm/v3/objects/deals/{deal_id}'
            params = {
                'properties': 'dealname,amount,closedate,pipeline,dealstage',
                'associations': 'contacts,companies,line_items'
            }

            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            deal = response.json()

            return ActionResult(
                success=True,
                data={
                    'id': deal['id'],
                    'properties': deal.get('properties', {}),
                    'associations': deal.get('associations', {}),
                    'created_at': deal.get('createdAt'),
                    'updated_at': deal.get('updatedAt')
                }
            )

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return ActionResult(
                success=False,
                error={"message": f"Deal with ID {deal_id} not found"}
            )

        return ActionResult(
            success=False,
            error={
                "message": f"HubSpot API error: {e.response.status_code} - {e.response.text}"
            }
        )
    except Exception as e:
        return ActionResult(
            success=False,
            error={"message": str(e)}
        )
