"""
Variable Resolver - Resolves {{trigger.field}} and {{stepName.field}} references

Inspired by Activepieces variable resolution system.
Supports:
- {{trigger.field}} - Access trigger output
- {{stepName.field}} - Access previous step output
- Nested paths: {{trigger.deal.properties.name}}
- Array access: {{trigger.line_items[0].name}}
"""

import re
from typing import Any, Dict, Optional, List
import logging

logger = logging.getLogger(__name__)


class VariableResolver:
    """
    Resolves variable references in flow definitions.

    Examples:
        {{trigger.deal_id}} -> "12345"
        {{trigger.contact.email}} -> "user@example.com"
        {{getContact.properties.firstname}} -> "John"
        {{trigger.line_items[0].name}} -> "Product A"
    """

    # Pattern to match {{variable.path}}
    VARIABLE_PATTERN = re.compile(r'\{\{([^}]+)\}\}')

    def __init__(self, trigger_output: Optional[Dict[str, Any]] = None,
                 steps_output: Optional[Dict[str, Any]] = None):
        """
        Initialize resolver with available data.

        Args:
            trigger_output: Output from trigger execution
            steps_output: Dict mapping step names to their outputs
        """
        self.trigger_output = trigger_output or {}
        self.steps_output = steps_output or {}

    def resolve(self, value: Any) -> Any:
        """
        Resolve variables in value (recursively handles dicts, lists, strings).

        Args:
            value: Value to resolve (can be string, dict, list, or primitive)

        Returns:
            Value with all {{variables}} resolved
        """
        if isinstance(value, str):
            return self._resolve_string(value)
        elif isinstance(value, dict):
            return {k: self.resolve(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self.resolve(item) for item in value]
        else:
            # Primitive value (int, bool, None, etc)
            return value

    def _resolve_string(self, text: str) -> Any:
        """
        Resolve variables in a string.

        If the ENTIRE string is a single variable reference, return the actual value.
        Otherwise, do string replacement.

        Examples:
            "{{trigger.amount}}" -> 1000 (int)
            "Amount: {{trigger.amount}}" -> "Amount: 1000" (string)
        """
        # Check if entire string is a single variable
        match = self.VARIABLE_PATTERN.fullmatch(text)
        if match:
            # Return actual value (preserves type)
            var_path = match.group(1).strip()
            return self._resolve_path(var_path)

        # Multiple variables or mixed text - do string replacement
        def replace_var(match):
            var_path = match.group(1).strip()
            value = self._resolve_path(var_path)
            return str(value) if value is not None else ''

        return self.VARIABLE_PATTERN.sub(replace_var, text)

    def _resolve_path(self, path: str) -> Any:
        """
        Resolve a variable path like "trigger.deal.name" or "stepName.output.id".

        Args:
            path: Variable path (without {{}}), e.g., "trigger.contact.email"

        Returns:
            Resolved value or None if not found
        """
        parts = path.split('.')

        if not parts:
            logger.warning(f"Empty variable path: {path}")
            return None

        # First part determines source (trigger or step name)
        source_name = parts[0]

        if source_name == 'trigger':
            source_data = self.trigger_output
        elif source_name in self.steps_output:
            source_data = self.steps_output[source_name]
        else:
            logger.warning(f"Unknown source in path: {source_name} (available: trigger, {list(self.steps_output.keys())})")
            return None

        # Navigate remaining path
        current = source_data
        for part in parts[1:]:
            # Handle array access: field[0]
            if '[' in part and part.endswith(']'):
                field_name, index_str = part.split('[')
                index_str = index_str.rstrip(']')

                # Navigate to field
                if isinstance(current, dict) and field_name in current:
                    current = current[field_name]
                else:
                    logger.debug(f"Field not found in path: {field_name}")
                    return None

                # Access array index
                try:
                    index = int(index_str)
                    if isinstance(current, list) and 0 <= index < len(current):
                        current = current[index]
                    else:
                        logger.debug(f"Invalid array access: index {index} in array of length {len(current) if isinstance(current, list) else 0}")
                        return None
                except (ValueError, TypeError):
                    logger.debug(f"Invalid array index: {index_str}")
                    return None
            else:
                # Regular field access
                if isinstance(current, dict):
                    current = current.get(part)
                    if current is None:
                        logger.debug(f"Field not found in path: {part}")
                        return None
                else:
                    logger.debug(f"Cannot navigate path {part} on non-dict value")
                    return None

        return current

    def validate(self, value: Any) -> List[str]:
        """
        Validate that all variables in value can be resolved.

        Returns:
            List of unresolved variable paths (empty if all valid)
        """
        unresolved = []

        def check_value(val):
            if isinstance(val, str):
                for match in self.VARIABLE_PATTERN.finditer(val):
                    var_path = match.group(1).strip()
                    resolved = self._resolve_path(var_path)
                    if resolved is None:
                        unresolved.append(var_path)
            elif isinstance(val, dict):
                for v in val.values():
                    check_value(v)
            elif isinstance(val, list):
                for item in val:
                    check_value(item)

        check_value(value)
        return unresolved

    def add_step_output(self, step_name: str, output: Dict[str, Any]):
        """
        Add output from a completed step.

        Args:
            step_name: Name of the step (used as {{stepName.field}})
            output: Step's output data
        """
        self.steps_output[step_name] = output
        logger.debug(f"Added step output for: {step_name}")

    def get_available_variables(self) -> List[str]:
        """
        Get list of all available variable paths for documentation/debugging.

        Returns:
            List of available variable prefixes
        """
        sources = ['trigger'] + list(self.steps_output.keys())
        return sources
