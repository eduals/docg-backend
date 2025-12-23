"""
Transform Module for Tag System

Provides transform functions that can be applied via pipe syntax:
{{value | transform:param}}
"""

from app.tags.transforms.base import BaseTransform, TransformRegistry
from app.tags.transforms.text import (
    UpperTransform,
    LowerTransform,
    CapitalizeTransform,
    TruncateTransform,
    ConcatTransform,
    TrimTransform,
    ReplaceTransform,
    DefaultTransform
)
from app.tags.transforms.date import (
    DateFormatTransform,
    DateAddTransform,
    RelativeDateTransform
)
from app.tags.transforms.number import (
    CurrencyTransform,
    NumberFormatTransform,
    RoundTransform,
    PercentTransform
)


# Create and populate the default registry
def create_default_registry() -> TransformRegistry:
    """Create a registry with all default transforms."""
    registry = TransformRegistry()

    # Text transforms
    registry.register(UpperTransform())
    registry.register(LowerTransform())
    registry.register(CapitalizeTransform())
    registry.register(TruncateTransform())
    registry.register(ConcatTransform())
    registry.register(TrimTransform())
    registry.register(ReplaceTransform())
    registry.register(DefaultTransform())

    # Date transforms
    registry.register(DateFormatTransform())
    registry.register(DateAddTransform())
    registry.register(RelativeDateTransform())

    # Number transforms
    registry.register(CurrencyTransform())
    registry.register(NumberFormatTransform())
    registry.register(RoundTransform())
    registry.register(PercentTransform())

    return registry


# Default registry instance
default_registry = create_default_registry()


__all__ = [
    'BaseTransform',
    'TransformRegistry',
    'default_registry',
    'create_default_registry',
    # Text
    'UpperTransform',
    'LowerTransform',
    'CapitalizeTransform',
    'TruncateTransform',
    'ConcatTransform',
    'TrimTransform',
    'ReplaceTransform',
    'DefaultTransform',
    # Date
    'DateFormatTransform',
    'DateAddTransform',
    'RelativeDateTransform',
    # Number
    'CurrencyTransform',
    'NumberFormatTransform',
    'RoundTransform',
    'PercentTransform',
]
