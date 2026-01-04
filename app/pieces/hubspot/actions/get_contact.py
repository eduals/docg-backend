"""
HubSpot - Get Contact action
"""
import httpx
from app.pieces.base import ActionResult, ExecutionContext


async def get_contact_handler(props: dict, ctx: ExecutionContext) -> ActionResult:
    """
    Get a HubSpot contact by ID or email
    """
    contact_id = props.get('contact_id')
    email = props.get('email')

    if not contact_id and not email:
        return ActionResult(
            success=False,
            error={"message": "Either contact_id or email is required"}
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

            if contact_id:
                # Get by ID
                url = f'https://api.hubapi.com/crm/v3/objects/contacts/{contact_id}'
                params = {'properties': 'email,firstname,lastname,phone,company'}
            else:
                # Search by email
                url = 'https://api.hubapi.com/crm/v3/objects/contacts/search'
                body = {
                    'filterGroups': [{
                        'filters': [{
                            'propertyName': 'email',
                            'operator': 'EQ',
                            'value': email
                        }]
                    }],
                    'properties': ['email', 'firstname', 'lastname', 'phone', 'company']
                }
                response = await client.post(url, json=body, headers=headers)
                response.raise_for_status()
                result = response.json()

                # Return first result
                if result.get('results'):
                    contact = result['results'][0]
                    return ActionResult(
                        success=True,
                        data={
                            'id': contact['id'],
                            'properties': contact.get('properties', {}),
                            'created_at': contact.get('createdAt'),
                            'updated_at': contact.get('updatedAt')
                        }
                    )
                else:
                    return ActionResult(
                        success=False,
                        error={"message": f"Contact with email {email} not found"}
                    )

            # Get by ID flow
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            contact = response.json()

            return ActionResult(
                success=True,
                data={
                    'id': contact['id'],
                    'properties': contact.get('properties', {}),
                    'created_at': contact.get('createdAt'),
                    'updated_at': contact.get('updatedAt')
                }
            )

    except httpx.HTTPStatusError as e:
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
