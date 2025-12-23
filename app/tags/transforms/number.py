"""
Number transforms for the tag system.

Provides number formatting:
- currency: Format as currency
- number: Format with decimal places
- round: Round to decimal places
- percent: Format as percentage
"""

from typing import Any, Dict, List
from decimal import Decimal, ROUND_HALF_UP
import re

from app.tags.transforms.base import BaseTransform, TransformError


# Currency configurations
CURRENCY_CONFIG = {
    'BRL': {
        'symbol': 'R$',
        'decimal_sep': ',',
        'thousand_sep': '.',
        'decimal_places': 2,
        'symbol_position': 'before',
        'symbol_space': True,
    },
    'USD': {
        'symbol': '$',
        'decimal_sep': '.',
        'thousand_sep': ',',
        'decimal_places': 2,
        'symbol_position': 'before',
        'symbol_space': False,
    },
    'EUR': {
        'symbol': '€',
        'decimal_sep': ',',
        'thousand_sep': '.',
        'decimal_places': 2,
        'symbol_position': 'after',
        'symbol_space': True,
    },
    'GBP': {
        'symbol': '£',
        'decimal_sep': '.',
        'thousand_sep': ',',
        'decimal_places': 2,
        'symbol_position': 'before',
        'symbol_space': False,
    },
}


def parse_number(value: Any) -> float:
    """
    Parse a value into a number.

    Handles:
    - int, float, Decimal
    - Strings with various formats
    """
    if value is None:
        return 0.0

    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, Decimal):
        return float(value)

    # Try string parsing
    value_str = str(value).strip()

    if not value_str:
        return 0.0

    # Remove currency symbols and spaces
    value_str = re.sub(r'[R$€£¥₹\s]', '', value_str)

    # Handle Brazilian format (1.234,56)
    if ',' in value_str and '.' in value_str:
        # Check which is the decimal separator (the last one)
        last_dot = value_str.rfind('.')
        last_comma = value_str.rfind(',')

        if last_comma > last_dot:
            # Brazilian format: 1.234,56
            value_str = value_str.replace('.', '').replace(',', '.')
        else:
            # US format: 1,234.56
            value_str = value_str.replace(',', '')
    elif ',' in value_str:
        # Could be Brazilian decimal or US thousand separator
        # If there are exactly 2 digits after the comma, treat as decimal
        parts = value_str.split(',')
        if len(parts) == 2 and len(parts[1]) <= 2:
            value_str = value_str.replace(',', '.')
        else:
            value_str = value_str.replace(',', '')

    try:
        return float(value_str)
    except ValueError:
        raise TransformError('number', f"Cannot parse '{value}' as number")


def format_number(
    value: float,
    decimal_places: int = 2,
    decimal_sep: str = ',',
    thousand_sep: str = '.'
) -> str:
    """Format a number with separators."""
    # Round to decimal places
    if decimal_places >= 0:
        value = round(value, decimal_places)

    # Split integer and decimal parts
    if decimal_places > 0:
        format_str = f"{{:.{decimal_places}f}}"
        formatted = format_str.format(value)
    else:
        formatted = str(int(round(value)))

    # Handle decimal separator
    if '.' in formatted:
        integer_part, decimal_part = formatted.split('.')
    else:
        integer_part = formatted
        decimal_part = None

    # Add thousand separators
    if thousand_sep:
        # Handle negative numbers
        is_negative = integer_part.startswith('-')
        if is_negative:
            integer_part = integer_part[1:]

        # Add separators from right to left
        chars = list(integer_part)
        result_chars = []
        for i, char in enumerate(reversed(chars)):
            if i > 0 and i % 3 == 0:
                result_chars.append(thousand_sep)
            result_chars.append(char)
        integer_part = ''.join(reversed(result_chars))

        if is_negative:
            integer_part = '-' + integer_part

    # Combine parts
    if decimal_part is not None:
        return f"{integer_part}{decimal_sep}{decimal_part}"
    else:
        return integer_part


class CurrencyTransform(BaseTransform):
    """
    Format a number as currency.

    Usage: {{amount | currency:"BRL"}}
           {{amount | currency:"USD"}}

    Params:
        - currency_code (str): ISO currency code (default: BRL)

    Supported currencies:
        - BRL: R$ 1.234,56
        - USD: $1,234.56
        - EUR: 1.234,56 €
        - GBP: £1,234.56
    """
    name = "currency"
    aliases = ["money", "moeda"]

    def transform(self, value: Any, params: List[Any], context: Dict[str, Any]) -> str:
        if value is None or value == "":
            return ""

        currency_code = str(params[0]).upper() if params else "BRL"
        config = CURRENCY_CONFIG.get(currency_code, CURRENCY_CONFIG['USD'])

        try:
            number = parse_number(value)
        except TransformError:
            return str(value)

        # Format the number
        formatted = format_number(
            number,
            decimal_places=config['decimal_places'],
            decimal_sep=config['decimal_sep'],
            thousand_sep=config['thousand_sep']
        )

        # Add currency symbol
        symbol = config['symbol']
        space = ' ' if config['symbol_space'] else ''

        if config['symbol_position'] == 'before':
            return f"{symbol}{space}{formatted}"
        else:
            return f"{formatted}{space}{symbol}"


class NumberFormatTransform(BaseTransform):
    """
    Format a number with decimal places.

    Usage: {{value | number:2}}
           {{value | number:0}}

    Params:
        - decimal_places (int): Number of decimal places (default: 2)
        - locale (str): Locale for formatting (default: pt_BR)
    """
    name = "number"
    aliases = ["num", "decimal"]

    def transform(self, value: Any, params: List[Any], context: Dict[str, Any]) -> str:
        if value is None or value == "":
            return ""

        decimal_places = int(params[0]) if params else 2

        # Get locale-specific separators
        locale = context.get('locale', 'pt_BR')
        if locale.startswith('pt'):
            decimal_sep = ','
            thousand_sep = '.'
        else:
            decimal_sep = '.'
            thousand_sep = ','

        try:
            number = parse_number(value)
        except TransformError:
            return str(value)

        return format_number(
            number,
            decimal_places=decimal_places,
            decimal_sep=decimal_sep,
            thousand_sep=thousand_sep
        )


class RoundTransform(BaseTransform):
    """
    Round a number to decimal places.

    Usage: {{value | round:2}}
           {{value | round:0}}

    Params:
        - decimal_places (int): Number of decimal places (default: 0)
    """
    name = "round"

    def transform(self, value: Any, params: List[Any], context: Dict[str, Any]) -> float:
        if value is None:
            return 0

        decimal_places = int(params[0]) if params else 0

        try:
            number = parse_number(value)
        except TransformError:
            return 0

        return round(number, decimal_places)


class PercentTransform(BaseTransform):
    """
    Format a number as percentage.

    Usage: {{value | percent}}      # 0.15 -> 15%
           {{value | percent:2}}    # 0.1567 -> 15.67%
           {{value | percent:0:false}}  # 15 (already percentage) -> 15%

    Params:
        - decimal_places (int): Number of decimal places (default: 0)
        - multiply (bool): Whether to multiply by 100 (default: true)
    """
    name = "percent"
    aliases = ["percentage", "pct"]

    def transform(self, value: Any, params: List[Any], context: Dict[str, Any]) -> str:
        if value is None or value == "":
            return ""

        decimal_places = int(params[0]) if params else 0

        # Check if we should multiply by 100
        multiply = True
        if len(params) > 1:
            multiply = str(params[1]).lower() not in ('false', '0', 'no')

        try:
            number = parse_number(value)
        except TransformError:
            return str(value)

        if multiply:
            number *= 100

        # Format based on locale
        locale = context.get('locale', 'pt_BR')
        if locale.startswith('pt'):
            decimal_sep = ','
        else:
            decimal_sep = '.'

        formatted = format_number(
            number,
            decimal_places=decimal_places,
            decimal_sep=decimal_sep,
            thousand_sep=''  # No thousand separator for percentages
        )

        return f"{formatted}%"


class AbsTransform(BaseTransform):
    """
    Get absolute value of a number.

    Usage: {{value | abs}}
    """
    name = "abs"
    aliases = ["absolute"]

    def transform(self, value: Any, params: List[Any], context: Dict[str, Any]) -> float:
        if value is None:
            return 0

        try:
            number = parse_number(value)
        except TransformError:
            return 0

        return abs(number)
