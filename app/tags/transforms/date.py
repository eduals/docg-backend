"""
Date transforms for the tag system.

Provides date formatting and manipulation:
- format: Format dates with patterns
- add: Add time to dates
- relative: Human-readable relative dates
"""

from typing import Any, Dict, List
from datetime import datetime, timedelta
from dateutil import parser as date_parser
from dateutil.relativedelta import relativedelta
import re

from app.tags.transforms.base import BaseTransform, TransformError


# Format pattern mappings (our format -> Python strftime)
FORMAT_MAPPINGS = {
    # Day
    'DD': '%d',      # 01-31
    'D': '%-d',      # 1-31 (no padding) - may not work on Windows
    'dddd': '%A',    # Monday, Tuesday, etc.
    'ddd': '%a',     # Mon, Tue, etc.

    # Month
    'MMMM': '%B',    # January, February, etc.
    'MMM': '%b',     # Jan, Feb, etc.
    'MM': '%m',      # 01-12
    'M': '%-m',      # 1-12 (no padding)

    # Year
    'YYYY': '%Y',    # 2025
    'YY': '%y',      # 25

    # Hour
    'HH': '%H',      # 00-23
    'H': '%-H',      # 0-23
    'hh': '%I',      # 01-12
    'h': '%-I',      # 1-12

    # Minute
    'mm': '%M',      # 00-59
    'm': '%-M',      # 0-59

    # Second
    'ss': '%S',      # 00-59
    's': '%-S',      # 0-59

    # AM/PM
    'A': '%p',       # AM, PM
    'a': '%p',       # am, pm (lowercase handled separately)

    # Timezone
    'Z': '%z',       # +0000
    'ZZ': '%Z',      # UTC, EST, etc.
}

# Month names for locales
MONTH_NAMES = {
    'pt_BR': [
        'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
        'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'
    ],
    'en_US': [
        'January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'
    ]
}

WEEKDAY_NAMES = {
    'pt_BR': [
        'Segunda-feira', 'Terça-feira', 'Quarta-feira', 'Quinta-feira',
        'Sexta-feira', 'Sábado', 'Domingo'
    ],
    'en_US': [
        'Monday', 'Tuesday', 'Wednesday', 'Thursday',
        'Friday', 'Saturday', 'Sunday'
    ]
}


def parse_date(value: Any) -> datetime:
    """
    Parse a value into a datetime object.

    Handles:
    - datetime objects
    - ISO format strings
    - Unix timestamps (milliseconds)
    - Various string formats
    """
    if isinstance(value, datetime):
        return value

    if value is None:
        raise ValueError("Cannot parse None as date")

    # Try Unix timestamp (milliseconds - common in HubSpot)
    if isinstance(value, (int, float)):
        # If it's a large number, assume milliseconds
        if value > 1e11:
            return datetime.fromtimestamp(value / 1000)
        return datetime.fromtimestamp(value)

    # Try string parsing
    value_str = str(value).strip()

    if not value_str:
        raise ValueError("Cannot parse empty string as date")

    # Try ISO format first
    try:
        return datetime.fromisoformat(value_str.replace('Z', '+00:00'))
    except ValueError:
        pass

    # Try dateutil parser (handles many formats)
    try:
        return date_parser.parse(value_str)
    except (ValueError, TypeError) as e:
        raise ValueError(f"Cannot parse '{value}' as date: {e}")


def format_date_with_locale(dt: datetime, format_str: str, locale: str = 'pt_BR') -> str:
    """
    Format a datetime with locale support.

    Handles month and weekday names in different locales.
    """
    result = format_str

    # Replace month names
    if 'MMMM' in result:
        month_name = MONTH_NAMES.get(locale, MONTH_NAMES['en_US'])[dt.month - 1]
        result = result.replace('MMMM', month_name)
    elif 'MMM' in result:
        month_name = MONTH_NAMES.get(locale, MONTH_NAMES['en_US'])[dt.month - 1][:3]
        result = result.replace('MMM', month_name)

    # Replace weekday names
    if 'dddd' in result:
        weekday_name = WEEKDAY_NAMES.get(locale, WEEKDAY_NAMES['en_US'])[dt.weekday()]
        result = result.replace('dddd', weekday_name)
    elif 'ddd' in result:
        weekday_name = WEEKDAY_NAMES.get(locale, WEEKDAY_NAMES['en_US'])[dt.weekday()][:3]
        result = result.replace('ddd', weekday_name)

    # Replace remaining patterns with strftime
    for pattern, strftime_code in sorted(FORMAT_MAPPINGS.items(), key=lambda x: -len(x[0])):
        if pattern in result and pattern not in ('MMMM', 'MMM', 'dddd', 'ddd'):
            try:
                formatted = dt.strftime(strftime_code)
                result = result.replace(pattern, formatted)
            except ValueError:
                # Some codes like %-d don't work on Windows
                # Fall back to padded version
                padded_code = strftime_code.replace('-', '')
                result = result.replace(pattern, dt.strftime(padded_code).lstrip('0') or '0')

    return result


class DateFormatTransform(BaseTransform):
    """
    Format a date value.

    Usage: {{date | format:"DD/MM/YYYY"}}
           {{date | format:"MMMM YYYY"}}
           {{date | format:"DD de MMMM de YYYY, HH:mm":"pt_BR"}}

    Params:
        - format (str): Date format pattern
        - locale (str): Locale for month/day names (default: pt_BR)

    Patterns:
        DD - Day (01-31)
        MM - Month (01-12)
        MMMM - Month name (Janeiro)
        YYYY - Year (2025)
        HH - Hour (00-23)
        mm - Minute (00-59)
        ss - Second (00-59)
    """
    name = "format"
    aliases = ["date_format", "dateformat"]

    def transform(self, value: Any, params: List[Any], context: Dict[str, Any]) -> str:
        if value is None or value == "":
            return ""

        # Default format
        format_str = params[0] if params else "DD/MM/YYYY"

        # Get locale from params or context
        locale = "pt_BR"
        if len(params) > 1:
            locale = str(params[1])
        elif 'locale' in context:
            locale = context['locale']

        try:
            dt = parse_date(value)
            return format_date_with_locale(dt, format_str, locale)
        except (ValueError, TypeError) as e:
            # Return original value if parsing fails
            return str(value)


class DateAddTransform(BaseTransform):
    """
    Add or subtract time from a date.

    Usage: {{date | add_days:30}}
           {{date | add_months:-1}}
           {{date | add_years:1}}

    This transform has multiple names for convenience:
    - add_days, add_months, add_years
    - add_hours, add_minutes
    """
    name = "add_days"
    aliases = ["add_months", "add_years", "add_hours", "add_minutes", "add_weeks"]

    def transform(self, value: Any, params: List[Any], context: Dict[str, Any]) -> datetime:
        if value is None:
            return None

        if not params:
            return parse_date(value)

        amount = int(params[0])
        dt = parse_date(value)

        # Determine unit from transform name in context
        transform_name = context.get('_transform_name', self.name)

        if 'days' in transform_name:
            return dt + timedelta(days=amount)
        elif 'weeks' in transform_name:
            return dt + timedelta(weeks=amount)
        elif 'months' in transform_name:
            return dt + relativedelta(months=amount)
        elif 'years' in transform_name:
            return dt + relativedelta(years=amount)
        elif 'hours' in transform_name:
            return dt + timedelta(hours=amount)
        elif 'minutes' in transform_name:
            return dt + timedelta(minutes=amount)
        else:
            return dt + timedelta(days=amount)


class RelativeDateTransform(BaseTransform):
    """
    Format date as relative time (e.g., "2 days ago", "in 3 months").

    Usage: {{date | relative}}
           {{date | relative:"pt_BR"}}

    Params:
        - locale (str): Locale for output (default: pt_BR)
    """
    name = "relative"
    aliases = ["timeago", "ago"]

    UNITS_PT = {
        'second': ('segundo', 'segundos'),
        'minute': ('minuto', 'minutos'),
        'hour': ('hora', 'horas'),
        'day': ('dia', 'dias'),
        'week': ('semana', 'semanas'),
        'month': ('mês', 'meses'),
        'year': ('ano', 'anos'),
    }

    UNITS_EN = {
        'second': ('second', 'seconds'),
        'minute': ('minute', 'minutes'),
        'hour': ('hour', 'hours'),
        'day': ('day', 'days'),
        'week': ('week', 'weeks'),
        'month': ('month', 'months'),
        'year': ('year', 'years'),
    }

    def transform(self, value: Any, params: List[Any], context: Dict[str, Any]) -> str:
        if value is None:
            return ""

        locale = params[0] if params else context.get('locale', 'pt_BR')
        units = self.UNITS_PT if locale.startswith('pt') else self.UNITS_EN

        try:
            dt = parse_date(value)
        except (ValueError, TypeError):
            return str(value)

        now = datetime.now()
        diff = now - dt
        is_past = diff.total_seconds() > 0

        # Get absolute difference
        total_seconds = abs(diff.total_seconds())

        # Determine the best unit
        if total_seconds < 60:
            count = int(total_seconds)
            unit = 'second'
        elif total_seconds < 3600:
            count = int(total_seconds / 60)
            unit = 'minute'
        elif total_seconds < 86400:
            count = int(total_seconds / 3600)
            unit = 'hour'
        elif total_seconds < 604800:
            count = int(total_seconds / 86400)
            unit = 'day'
        elif total_seconds < 2592000:
            count = int(total_seconds / 604800)
            unit = 'week'
        elif total_seconds < 31536000:
            count = int(total_seconds / 2592000)
            unit = 'month'
        else:
            count = int(total_seconds / 31536000)
            unit = 'year'

        # Get singular or plural form
        unit_name = units[unit][0 if count == 1 else 1]

        # Format based on past/future and locale
        if locale.startswith('pt'):
            if is_past:
                return f"há {count} {unit_name}"
            else:
                return f"em {count} {unit_name}"
        else:
            if is_past:
                return f"{count} {unit_name} ago"
            else:
                return f"in {count} {unit_name}"
