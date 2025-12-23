"""
Text transforms for the tag system.

Provides string manipulation transforms:
- upper, lower, capitalize
- truncate, trim
- concat, replace
- default
"""

from typing import Any, Dict, List

from app.tags.transforms.base import BaseTransform, TransformError


class UpperTransform(BaseTransform):
    """
    Convert value to uppercase.

    Usage: {{name | upper}}
    """
    name = "upper"
    aliases = ["uppercase"]

    def transform(self, value: Any, params: List[Any], context: Dict[str, Any]) -> str:
        if value is None:
            return ""
        return str(value).upper()


class LowerTransform(BaseTransform):
    """
    Convert value to lowercase.

    Usage: {{name | lower}}
    """
    name = "lower"
    aliases = ["lowercase"]

    def transform(self, value: Any, params: List[Any], context: Dict[str, Any]) -> str:
        if value is None:
            return ""
        return str(value).lower()


class CapitalizeTransform(BaseTransform):
    """
    Capitalize first letter of each word.

    Usage: {{name | capitalize}}
    """
    name = "capitalize"
    aliases = ["title", "titlecase"]

    def transform(self, value: Any, params: List[Any], context: Dict[str, Any]) -> str:
        if value is None:
            return ""
        return str(value).title()


class TruncateTransform(BaseTransform):
    """
    Truncate string to a maximum length.

    Usage: {{description | truncate:100}}
           {{description | truncate:100:"..."}}

    Params:
        - length (int): Maximum length
        - suffix (str): Suffix to add when truncated (default: "...")
    """
    name = "truncate"

    def transform(self, value: Any, params: List[Any], context: Dict[str, Any]) -> str:
        if value is None:
            return ""

        text = str(value)

        if not params:
            return text

        max_length = int(params[0])
        suffix = params[1] if len(params) > 1 else "..."

        if len(text) <= max_length:
            return text

        # Truncate and add suffix
        truncated_length = max_length - len(suffix)
        if truncated_length <= 0:
            return suffix[:max_length]

        return text[:truncated_length] + suffix


class TrimTransform(BaseTransform):
    """
    Remove leading and trailing whitespace.

    Usage: {{value | trim}}
    """
    name = "trim"
    aliases = ["strip"]

    def transform(self, value: Any, params: List[Any], context: Dict[str, Any]) -> str:
        if value is None:
            return ""
        return str(value).strip()


class ConcatTransform(BaseTransform):
    """
    Concatenate a string to the value.

    Usage: {{firstname | concat:" "}}
           {{firstname | concat:" " | concat:lastname}}

    Params:
        - text (str): Text to append
    """
    name = "concat"
    aliases = ["append"]

    def transform(self, value: Any, params: List[Any], context: Dict[str, Any]) -> str:
        if value is None:
            value = ""

        text = str(value)

        if not params:
            return text

        # Concatenate all params
        for param in params:
            text += str(param)

        return text


class ReplaceTransform(BaseTransform):
    """
    Replace occurrences of a string.

    Usage: {{value | replace:"old":"new"}}

    Params:
        - search (str): String to find
        - replacement (str): String to replace with
    """
    name = "replace"

    def transform(self, value: Any, params: List[Any], context: Dict[str, Any]) -> str:
        if value is None:
            return ""

        text = str(value)

        if len(params) < 2:
            raise TransformError(self.name, "Replace requires search and replacement parameters")

        search = str(params[0])
        replacement = str(params[1])

        return text.replace(search, replacement)


class DefaultTransform(BaseTransform):
    """
    Provide a default value if the input is empty or None.

    Usage: {{value | default:"N/A"}}
           {{value | default:"No value provided"}}

    Params:
        - default_value: Value to use if input is empty/None
    """
    name = "default"
    aliases = ["fallback", "or"]

    def transform(self, value: Any, params: List[Any], context: Dict[str, Any]) -> Any:
        # Check if value is "empty"
        is_empty = (
            value is None or
            value == "" or
            (isinstance(value, (list, dict)) and len(value) == 0)
        )

        if is_empty and params:
            return params[0]

        return value if value is not None else ""


class PadLeftTransform(BaseTransform):
    """
    Pad string on the left to reach a minimum length.

    Usage: {{number | padleft:5:"0"}}

    Params:
        - length (int): Minimum length
        - char (str): Character to pad with (default: " ")
    """
    name = "padleft"
    aliases = ["ljust"]

    def transform(self, value: Any, params: List[Any], context: Dict[str, Any]) -> str:
        if value is None:
            value = ""

        text = str(value)

        if not params:
            return text

        length = int(params[0])
        char = str(params[1]) if len(params) > 1 else " "

        return text.rjust(length, char[0] if char else " ")


class PadRightTransform(BaseTransform):
    """
    Pad string on the right to reach a minimum length.

    Usage: {{text | padright:20}}

    Params:
        - length (int): Minimum length
        - char (str): Character to pad with (default: " ")
    """
    name = "padright"
    aliases = ["rjust"]

    def transform(self, value: Any, params: List[Any], context: Dict[str, Any]) -> str:
        if value is None:
            value = ""

        text = str(value)

        if not params:
            return text

        length = int(params[0])
        char = str(params[1]) if len(params) > 1 else " "

        return text.ljust(length, char[0] if char else " ")


class SplitTransform(BaseTransform):
    """
    Split string into array by delimiter.

    Usage: {{tags | split:","}}

    Params:
        - delimiter (str): Delimiter to split by (default: ",")
    """
    name = "split"

    def transform(self, value: Any, params: List[Any], context: Dict[str, Any]) -> List[str]:
        if value is None:
            return []

        text = str(value)
        delimiter = str(params[0]) if params else ","

        return text.split(delimiter)


class JoinTransform(BaseTransform):
    """
    Join array elements into string.

    Usage: {{items | join:", "}}

    Params:
        - separator (str): Separator between elements (default: ", ")
    """
    name = "join"

    def transform(self, value: Any, params: List[Any], context: Dict[str, Any]) -> str:
        if value is None:
            return ""

        if not isinstance(value, (list, tuple)):
            return str(value)

        separator = str(params[0]) if params else ", "

        return separator.join(str(item) for item in value)
