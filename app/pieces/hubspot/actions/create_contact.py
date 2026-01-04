"""
HubSpot - Create Contact action
"""
import httpx
from app.pieces.base import ActionResult, ExecutionContext


async def create_contact_handler(props: dict, ctx: ExecutionContext) -> ActionResult:
    """
    Create a new contact in HubSpot
    """
    email = props.get('email')
    if not email:
        return ActionResult(
            success=False,
            error={"message": "Email is required"}
        )

    # Build properties
    properties = {
        'email': email
    }

    # Add optional fields
    if props.get('firstname'):
        properties['firstname'] = props['firstname']
    if props.get('lastname'):
        properties['lastname'] = props['lastname']
    if props.get('phone'):
        properties['phone'] = props['phone']
    if props.get('company'):
        properties['company'] = props['company']

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

            url = 'https://api.hubapi.com/crm/v3/objects/contacts'
            body = {'properties': properties}

            response = await client.post(url, json=body, headers=headers)
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
        error_text = e.response.text

        # Check for duplicate email error
        if e.response.status_code == 409:
            return ActionResult(
                success=False,
                error={"message": f"Contact with email {email} already exists"}
            )

        return ActionResult(
            success=False,
            error={
                "message": f"HubSpot API error: {e.response.status_code} - {error_text}"
            }
        )
    except Exception as e:
        return ActionResult(
            success=False,
            error={"message": str(e)}
        )
