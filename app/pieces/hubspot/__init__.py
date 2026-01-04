"""
HubSpot Piece
Integration with HubSpot CRM
"""
from app.pieces.base import (
    Piece,
    Action,
    Auth,
    AuthType,
    OAuth2Config,
    Property,
    PropertyType,
    register_piece,
    short_text_property,
    dropdown_property,
)
from .actions.get_contact import get_contact_handler
from .actions.create_contact import create_contact_handler
from .actions.get_deal import get_deal_handler


# Define the HubSpot piece
hubspot_piece = Piece(
    name="hubspot",
    display_name="HubSpot",
    description="Connect to HubSpot CRM to manage contacts, deals, and more",
    version="1.0.0",
    logo_url="https://www.hubspot.com/hubfs/assets/hubspot.com/style-guide/logo/logo-sprocket-only.svg",
    auth=Auth(
        type=AuthType.OAUTH2,
        required=True,
        oauth2_config=OAuth2Config(
            auth_url="https://app.hubspot.com/oauth/authorize",
            token_url="https://api.hubapi.com/oauth/v1/token",
            scope=[
                "crm.objects.contacts.read",
                "crm.objects.contacts.write",
                "crm.objects.companies.read",
                "crm.objects.companies.write",
                "crm.objects.deals.read",
                "crm.objects.deals.write",
                "tickets",  # For tickets
                "e-commerce",  # For line items
            ]
        )
    ),
    categories=["CRM", "Sales", "Marketing"],
    actions=[
        # Contact actions
        Action(
            name="get_contact",
            display_name="Get Contact",
            description="Get a contact by ID or email",
            require_auth=True,
            properties=[
                short_text_property(
                    name="contact_id",
                    display_name="Contact ID",
                    description="HubSpot contact ID (leave empty if using email)",
                    required=False
                ),
                short_text_property(
                    name="email",
                    display_name="Email",
                    description="Contact email (leave empty if using ID)",
                    required=False
                )
            ],
            handler=get_contact_handler
        ),
        Action(
            name="create_contact",
            display_name="Create Contact",
            description="Create a new contact in HubSpot",
            require_auth=True,
            properties=[
                short_text_property(
                    name="email",
                    display_name="Email",
                    description="Contact email address",
                    required=True
                ),
                short_text_property(
                    name="firstname",
                    display_name="First Name",
                    description="Contact first name",
                    required=False
                ),
                short_text_property(
                    name="lastname",
                    display_name="Last Name",
                    description="Contact last name",
                    required=False
                ),
                short_text_property(
                    name="phone",
                    display_name="Phone",
                    description="Contact phone number",
                    required=False
                ),
                short_text_property(
                    name="company",
                    display_name="Company",
                    description="Company name",
                    required=False
                )
            ],
            handler=create_contact_handler
        ),

        # Deal actions
        Action(
            name="get_deal",
            display_name="Get Deal",
            description="Get a deal by ID",
            require_auth=True,
            properties=[
                short_text_property(
                    name="deal_id",
                    display_name="Deal ID",
                    description="HubSpot deal ID",
                    required=True
                )
            ],
            handler=get_deal_handler
        ),
    ],
    triggers=[
        # Triggers can be added later
    ]
)

# Register the piece
register_piece(hubspot_piece)
