"""
Context Module for Tag System

Provides context building and data normalization for different sources.
"""

from app.tags.context.builder import ContextBuilder
from app.tags.context.normalizer import (
    DataNormalizer,
    HubSpotNormalizer,
    WebhookNormalizer,
    GoogleFormsNormalizer,
    StripeNormalizer,
    GenericNormalizer,
    get_normalizer_for_source
)
from app.tags.context.global_vars import GlobalVarsProvider

__all__ = [
    'ContextBuilder',
    'DataNormalizer',
    'HubSpotNormalizer',
    'WebhookNormalizer',
    'GoogleFormsNormalizer',
    'StripeNormalizer',
    'GenericNormalizer',
    'get_normalizer_for_source',
    'GlobalVarsProvider'
]
