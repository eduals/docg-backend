"""
Built-in functions for the tag system.

Provides functions that can be used in formulas:
{{= SUM(items.price)}}
{{= ROUND(amount, 2)}}
{{= IF(condition, true_value, false_value)}}
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime
import math


class FunctionError(Exception):
    """Error during function execution."""
    def __init__(self, function_name: str, message: str):
        self.function_name = function_name
        super().__init__(f"Function '{function_name}' failed: {message}")


class TagFunction(ABC):
    """Base class for tag functions."""

    name: str = ""
    min_args: int = 0
    max_args: int = None  # None means unlimited

    @abstractmethod
    def execute(self, args: List[Any], context: Dict[str, Any]) -> Any:
        """Execute the function with given arguments."""
        pass

    def validate_args(self, args: List[Any]):
        """Validate argument count."""
        if len(args) < self.min_args:
            raise FunctionError(
                self.name,
                f"Expected at least {self.min_args} arguments, got {len(args)}"
            )
        if self.max_args is not None and len(args) > self.max_args:
            raise FunctionError(
                self.name,
                f"Expected at most {self.max_args} arguments, got {len(args)}"
            )


class FunctionRegistry:
    """Registry of available functions."""

    def __init__(self):
        self._functions: Dict[str, TagFunction] = {}

    def register(self, func: TagFunction):
        """Register a function."""
        self._functions[func.name.upper()] = func

    def get(self, name: str) -> Optional[TagFunction]:
        """Get a function by name."""
        return self._functions.get(name.upper())

    def has(self, name: str) -> bool:
        """Check if a function exists."""
        return name.upper() in self._functions

    def execute(self, name: str, args: List[Any], context: Dict[str, Any]) -> Any:
        """Execute a function by name."""
        func = self.get(name)
        if not func:
            raise FunctionError(name, f"Unknown function: {name}")

        func.validate_args(args)
        return func.execute(args, context)


# ============================================================================
# Mathematical Functions
# ============================================================================

class SumFunction(TagFunction):
    """
    Sum values in an array or sum multiple arguments.

    Usage:
        SUM(items.price)     # Sum array field
        SUM(1, 2, 3)         # Sum arguments
    """
    name = "SUM"
    min_args = 1

    def execute(self, args: List[Any], context: Dict[str, Any]) -> float:
        total = 0
        for arg in args:
            if isinstance(arg, (list, tuple)):
                total += sum(float(x) for x in arg if x is not None)
            elif arg is not None:
                total += float(arg)
        return total


class AvgFunction(TagFunction):
    """
    Calculate average of values.

    Usage:
        AVG(items.price)     # Average of array field
        AVG(1, 2, 3)         # Average of arguments
    """
    name = "AVG"
    min_args = 1

    def execute(self, args: List[Any], context: Dict[str, Any]) -> float:
        values = []
        for arg in args:
            if isinstance(arg, (list, tuple)):
                values.extend(float(x) for x in arg if x is not None)
            elif arg is not None:
                values.append(float(arg))

        if not values:
            return 0
        return sum(values) / len(values)


class MinFunction(TagFunction):
    """Get minimum value."""
    name = "MIN"
    min_args = 1

    def execute(self, args: List[Any], context: Dict[str, Any]) -> float:
        values = []
        for arg in args:
            if isinstance(arg, (list, tuple)):
                values.extend(float(x) for x in arg if x is not None)
            elif arg is not None:
                values.append(float(arg))

        if not values:
            return 0
        return min(values)


class MaxFunction(TagFunction):
    """Get maximum value."""
    name = "MAX"
    min_args = 1

    def execute(self, args: List[Any], context: Dict[str, Any]) -> float:
        values = []
        for arg in args:
            if isinstance(arg, (list, tuple)):
                values.extend(float(x) for x in arg if x is not None)
            elif arg is not None:
                values.append(float(arg))

        if not values:
            return 0
        return max(values)


class RoundFunction(TagFunction):
    """
    Round a number to specified decimal places.

    Usage:
        ROUND(value)         # Round to integer
        ROUND(value, 2)      # Round to 2 decimal places
    """
    name = "ROUND"
    min_args = 1
    max_args = 2

    def execute(self, args: List[Any], context: Dict[str, Any]) -> float:
        value = float(args[0]) if args[0] is not None else 0
        decimals = int(args[1]) if len(args) > 1 else 0
        return round(value, decimals)


class AbsFunction(TagFunction):
    """Get absolute value."""
    name = "ABS"
    min_args = 1
    max_args = 1

    def execute(self, args: List[Any], context: Dict[str, Any]) -> float:
        return abs(float(args[0])) if args[0] is not None else 0


class FloorFunction(TagFunction):
    """Round down to nearest integer."""
    name = "FLOOR"
    min_args = 1
    max_args = 1

    def execute(self, args: List[Any], context: Dict[str, Any]) -> int:
        return math.floor(float(args[0])) if args[0] is not None else 0


class CeilFunction(TagFunction):
    """Round up to nearest integer."""
    name = "CEIL"
    min_args = 1
    max_args = 1

    def execute(self, args: List[Any], context: Dict[str, Any]) -> int:
        return math.ceil(float(args[0])) if args[0] is not None else 0


class CountFunction(TagFunction):
    """
    Count items in an array or non-null arguments.

    Usage:
        COUNT(items)         # Count items in array
        COUNT(a, b, c)       # Count non-null arguments
    """
    name = "COUNT"
    min_args = 1

    def execute(self, args: List[Any], context: Dict[str, Any]) -> int:
        total = 0
        for arg in args:
            if isinstance(arg, (list, tuple)):
                total += len([x for x in arg if x is not None])
            elif arg is not None:
                total += 1
        return total


# ============================================================================
# Conditional Functions
# ============================================================================

class IfFunction(TagFunction):
    """
    Conditional function.

    Usage:
        IF(condition, true_value, false_value)
        IF(amount > 1000, "VIP", "Standard")
    """
    name = "IF"
    min_args = 2
    max_args = 3

    def execute(self, args: List[Any], context: Dict[str, Any]) -> Any:
        condition = args[0]
        true_value = args[1]
        false_value = args[2] if len(args) > 2 else ""

        # Evaluate condition as boolean
        if self._is_truthy(condition):
            return true_value
        return false_value

    def _is_truthy(self, value: Any) -> bool:
        """Check if a value is truthy."""
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            return value.lower() not in ('', 'false', '0', 'no', 'null', 'none')
        if isinstance(value, (list, dict)):
            return len(value) > 0
        return bool(value)


class CoalesceFunction(TagFunction):
    """
    Return first non-null, non-empty value.

    Usage:
        COALESCE(value1, value2, default)
    """
    name = "COALESCE"
    min_args = 1

    def execute(self, args: List[Any], context: Dict[str, Any]) -> Any:
        for arg in args:
            if arg is not None and arg != "":
                return arg
        return None


# ============================================================================
# String Functions
# ============================================================================

class ConcatFunction(TagFunction):
    """
    Concatenate strings.

    Usage:
        CONCAT(first, " ", last)
    """
    name = "CONCAT"
    min_args = 1

    def execute(self, args: List[Any], context: Dict[str, Any]) -> str:
        return ''.join(str(arg) if arg is not None else '' for arg in args)


class LenFunction(TagFunction):
    """
    Get length of string or array.

    Usage:
        LEN(text)
        LEN(items)
    """
    name = "LEN"
    min_args = 1
    max_args = 1

    def execute(self, args: List[Any], context: Dict[str, Any]) -> int:
        value = args[0]
        if value is None:
            return 0
        if isinstance(value, (str, list, tuple)):
            return len(value)
        return len(str(value))


class LeftFunction(TagFunction):
    """
    Get left part of string.

    Usage:
        LEFT(text, 5)
    """
    name = "LEFT"
    min_args = 2
    max_args = 2

    def execute(self, args: List[Any], context: Dict[str, Any]) -> str:
        text = str(args[0]) if args[0] is not None else ""
        length = int(args[1])
        return text[:length]


class RightFunction(TagFunction):
    """
    Get right part of string.

    Usage:
        RIGHT(text, 5)
    """
    name = "RIGHT"
    min_args = 2
    max_args = 2

    def execute(self, args: List[Any], context: Dict[str, Any]) -> str:
        text = str(args[0]) if args[0] is not None else ""
        length = int(args[1])
        return text[-length:] if length > 0 else ""


class SubstrFunction(TagFunction):
    """
    Get substring.

    Usage:
        SUBSTR(text, start, length)
        SUBSTR(text, start)  # To end
    """
    name = "SUBSTR"
    min_args = 2
    max_args = 3

    def execute(self, args: List[Any], context: Dict[str, Any]) -> str:
        text = str(args[0]) if args[0] is not None else ""
        start = int(args[1])

        if len(args) > 2:
            length = int(args[2])
            return text[start:start + length]
        return text[start:]


# ============================================================================
# Date Functions
# ============================================================================

class NowFunction(TagFunction):
    """
    Get current datetime.

    Usage:
        NOW()
    """
    name = "NOW"
    min_args = 0
    max_args = 0

    def execute(self, args: List[Any], context: Dict[str, Any]) -> datetime:
        return datetime.now()


class TodayFunction(TagFunction):
    """
    Get current date (without time).

    Usage:
        TODAY()
    """
    name = "TODAY"
    min_args = 0
    max_args = 0

    def execute(self, args: List[Any], context: Dict[str, Any]) -> datetime:
        return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)


# ============================================================================
# Default Registry
# ============================================================================

def create_default_function_registry() -> FunctionRegistry:
    """Create a registry with all default functions."""
    registry = FunctionRegistry()

    # Math functions
    registry.register(SumFunction())
    registry.register(AvgFunction())
    registry.register(MinFunction())
    registry.register(MaxFunction())
    registry.register(RoundFunction())
    registry.register(AbsFunction())
    registry.register(FloorFunction())
    registry.register(CeilFunction())
    registry.register(CountFunction())

    # Conditional functions
    registry.register(IfFunction())
    registry.register(CoalesceFunction())

    # String functions
    registry.register(ConcatFunction())
    registry.register(LenFunction())
    registry.register(LeftFunction())
    registry.register(RightFunction())
    registry.register(SubstrFunction())

    # Date functions
    registry.register(NowFunction())
    registry.register(TodayFunction())

    return registry


# Default instance
default_function_registry = create_default_function_registry()
