"""
HubSpot Common - Helpers compartilhados do app HubSpot.
"""

from .api_client import HubSpotAPIClient
from .associations import (
    AssociationsHelper,
    get_deal_contacts,
    get_deal_company,
    get_deal_line_items,
    get_contact_company,
    get_contact_deals,
)

__all__ = [
    'HubSpotAPIClient',
    'AssociationsHelper',
    'get_deal_contacts',
    'get_deal_company',
    'get_deal_line_items',
    'get_contact_company',
    'get_contact_deals',
]
