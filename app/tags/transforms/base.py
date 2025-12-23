"""
Base classes for transforms.

Transforms are operations applied to values via pipe syntax:
{{value | transform:param}}
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class TransformError(Exception):
    """Error during transform execution."""
    def __init__(self, transform_name: str, message: str, value: Any = None):
        self.transform_name = transform_name
        self.value = value
        super().__init__(f"Transform '{transform_name}' failed: {message}")


class BaseTransform(ABC):
    """
    Base class for all transforms.

    Subclasses must implement:
    - name: The transform name (e.g., 'upper', 'format')
    - transform(): The transformation logic
    """

    name: str = ""
    aliases: List[str] = []

    @abstractmethod
    def transform(self, value: Any, params: List[Any], context: Dict[str, Any]) -> Any:
        """
        Apply the transformation to a value.

        Args:
            value: The value to transform
            params: Parameters passed after colons (e.g., format:"DD/MM/YYYY" -> ["DD/MM/YYYY"])
            context: The evaluation context with all available data

        Returns:
            The transformed value
        """
        pass

    def __repr__(self):
        return f"<Transform: {self.name}>"


class TransformRegistry:
    """
    Registry of available transforms.

    Allows looking up transforms by name and registering custom transforms.
    """

    def __init__(self):
        self._transforms: Dict[str, BaseTransform] = {}

    def register(self, transform: BaseTransform):
        """Register a transform."""
        self._transforms[transform.name.lower()] = transform

        # Register aliases
        for alias in getattr(transform, 'aliases', []):
            self._transforms[alias.lower()] = transform

    def get(self, name: str) -> Optional[BaseTransform]:
        """Get a transform by name."""
        return self._transforms.get(name.lower())

    def has(self, name: str) -> bool:
        """Check if a transform exists."""
        return name.lower() in self._transforms

    def list_transforms(self) -> List[str]:
        """List all registered transform names."""
        return list(self._transforms.keys())

    def apply(self, name: str, value: Any, params: List[Any], context: Dict[str, Any]) -> Any:
        """
        Apply a transform by name.

        Args:
            name: Transform name
            value: Value to transform
            params: Transform parameters
            context: Evaluation context

        Returns:
            Transformed value

        Raises:
            TransformError: If transform not found or fails
        """
        transform = self.get(name)
        if not transform:
            raise TransformError(name, f"Unknown transform: {name}")

        try:
            return transform.transform(value, params, context)
        except TransformError:
            raise
        except Exception as e:
            raise TransformError(name, str(e), value)
