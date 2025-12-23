"""
HubSpot Triggers - Triggers disponíveis para o app HubSpot.
"""

from . import new_deal
from . import new_contact
from . import updated_deal

__all__ = [
    'new_deal',
    'new_contact',
    'updated_deal',
]
