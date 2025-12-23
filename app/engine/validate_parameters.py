"""
Validate Parameters - Valida parâmetros contra schema de ActionArguments.

Valida:
- Campos required
- Tipos de dados (number, boolean, etc)
- Min/max values e lengths
- Patterns (regex)
"""

from typing import Dict, Any, List, Optional
import re
import logging

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Erro de validação de parâmetros"""
    def __init__(self, errors: Dict[str, List[str]]):
        self.errors = errors
        message = "; ".join(
            f"{field}: {', '.join(msgs)}"
            for field, msgs in errors.items()
        )
        super().__init__(f"Validation failed: {message}")


def validate_parameters(
    parameters: Dict[str, Any],
    arguments: List[Any],
    skip_empty_optionals: bool = True,
) -> Dict[str, List[str]]:
    """
    Valida parâmetros contra schema de arguments.

    Args:
        parameters: Parâmetros a validar
        arguments: Lista de ActionArgument definindo o schema
        skip_empty_optionals: Se True, não valida campos opcionais vazios

    Returns:
        Dict de erros: {'field': ['error1', 'error2']}
        Dict vazio se válido
    """
    from app.apps.base import ArgumentType

    errors: Dict[str, List[str]] = {}

    for arg in arguments:
        key = arg.key
        value = parameters.get(key)
        field_errors = []

        # Required check
        if arg.required:
            if value is None or value == '' or value == []:
                field_errors.append(f"'{arg.label}' is required")
                errors[key] = field_errors
                continue  # Skip other validations if required failed

        # Skip optional empty fields
        if skip_empty_optionals and (value is None or value == ''):
            continue

        # Type validation
        if value is not None:
            arg_type = arg.type if hasattr(arg.type, 'value') else arg.type

            if arg_type == ArgumentType.NUMBER or arg_type == 'number':
                if not isinstance(value, (int, float)):
                    # Try to convert string to number
                    if isinstance(value, str):
                        try:
                            float(value)
                        except ValueError:
                            field_errors.append(f"'{arg.label}' must be a number")

            elif arg_type == ArgumentType.BOOLEAN or arg_type == 'boolean':
                if not isinstance(value, bool):
                    if isinstance(value, str) and value.lower() not in ['true', 'false', '1', '0']:
                        field_errors.append(f"'{arg.label}' must be a boolean")

            elif arg_type == ArgumentType.JSON or arg_type == 'json':
                if isinstance(value, str):
                    import json
                    try:
                        json.loads(value)
                    except json.JSONDecodeError:
                        field_errors.append(f"'{arg.label}' must be valid JSON")

        # Min/Max value validation (for numbers)
        if value is not None and isinstance(value, (int, float)):
            if arg.min_value is not None and value < arg.min_value:
                field_errors.append(f"'{arg.label}' must be >= {arg.min_value}")

            if arg.max_value is not None and value > arg.max_value:
                field_errors.append(f"'{arg.label}' must be <= {arg.max_value}")

        # Min/Max length validation (for strings)
        if value is not None and isinstance(value, str):
            if arg.min_length is not None and len(value) < arg.min_length:
                field_errors.append(f"'{arg.label}' must have at least {arg.min_length} characters")

            if arg.max_length is not None and len(value) > arg.max_length:
                field_errors.append(f"'{arg.label}' must have at most {arg.max_length} characters")

        # Pattern validation
        if value is not None and arg.pattern:
            if isinstance(value, str):
                try:
                    if not re.match(arg.pattern, value):
                        field_errors.append(f"'{arg.label}' format is invalid")
                except re.error:
                    logger.warning(f"Invalid regex pattern for {key}: {arg.pattern}")

        if field_errors:
            errors[key] = field_errors

    return errors


def validate_and_raise(
    parameters: Dict[str, Any],
    arguments: List[Any],
) -> None:
    """
    Valida e levanta ValidationError se houver erros.

    Args:
        parameters: Parâmetros a validar
        arguments: Lista de ActionArgument

    Raises:
        ValidationError: Se validação falhar
    """
    errors = validate_parameters(parameters, arguments)
    if errors:
        raise ValidationError(errors)
