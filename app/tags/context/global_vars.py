"""
Global Variables Provider for the tag system.

Provides built-in global variables like:
- $timestamp, $date, $time
- $document_number
- $workflow_name
- $uuid
"""

from datetime import datetime
from typing import Any, Dict, Optional
import uuid as uuid_module


class GlobalVarsProvider:
    """
    Provider for global variables in the tag system.

    Global variables are prefixed with $ and available in all contexts:
    {{$timestamp}}, {{$date}}, {{$uuid}}
    """

    def __init__(
        self,
        workflow_context: Optional[Dict[str, Any]] = None,
        execution_context: Optional[Dict[str, Any]] = None,
        custom_vars: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize the provider.

        Args:
            workflow_context: Workflow metadata (name, id, etc.)
            execution_context: Execution metadata (id, started_at, etc.)
            custom_vars: Custom global variables to include
        """
        self.workflow_context = workflow_context or {}
        self.execution_context = execution_context or {}
        self.custom_vars = custom_vars or {}
        self._document_counter = 0

    def get_all(self) -> Dict[str, Any]:
        """
        Get all global variables as a dictionary.

        Returns:
            Dictionary of global variable name -> value
        """
        now = datetime.now()

        globals_dict = {
            # Timestamps
            'timestamp': now.isoformat(),
            'date': now.strftime('%Y-%m-%d'),
            'date_br': now.strftime('%d/%m/%Y'),
            'time': now.strftime('%H:%M'),
            'datetime': now.strftime('%Y-%m-%d %H:%M:%S'),
            'datetime_br': now.strftime('%d/%m/%Y %H:%M'),

            # Date components
            'year': now.year,
            'month': now.month,
            'month_name': self._get_month_name(now.month),
            'month_name_short': self._get_month_name(now.month)[:3],
            'day': now.day,
            'weekday': now.strftime('%A'),
            'weekday_br': self._get_weekday_name(now.weekday()),

            # Unique identifiers
            'uuid': str(uuid_module.uuid4()),

            # Document numbering
            'document_number': self._get_document_number(),

            # Workflow info
            'workflow_name': self.workflow_context.get('name', ''),
            'workflow_id': self.workflow_context.get('id', ''),

            # Execution info
            'execution_id': self.execution_context.get('id', ''),
            'execution_started_at': self.execution_context.get('started_at', ''),

            # User info (if available)
            'user_name': self.execution_context.get('user_name', ''),
            'user_email': self.execution_context.get('user_email', ''),

            # Organization info (if available)
            'organization_name': self.execution_context.get('organization_name', ''),
        }

        # Add custom vars (can override defaults)
        globals_dict.update(self.custom_vars)

        return globals_dict

    def get(self, name: str) -> Any:
        """
        Get a specific global variable by name.

        Args:
            name: Variable name (without $ prefix)

        Returns:
            Variable value or None if not found
        """
        all_vars = self.get_all()
        return all_vars.get(name)

    def set_custom(self, name: str, value: Any):
        """
        Set a custom global variable.

        Args:
            name: Variable name
            value: Variable value
        """
        self.custom_vars[name] = value

    def _get_document_number(self) -> int:
        """Get or generate document number."""
        # Check if provided in execution context
        if 'document_number' in self.execution_context:
            return self.execution_context['document_number']

        # Otherwise use counter
        self._document_counter += 1
        return self._document_counter

    def _get_month_name(self, month: int, locale: str = 'pt_BR') -> str:
        """Get month name for locale."""
        months_pt = [
            'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
            'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'
        ]
        months_en = [
            'January', 'February', 'March', 'April', 'May', 'June',
            'July', 'August', 'September', 'October', 'November', 'December'
        ]

        if locale.startswith('pt'):
            return months_pt[month - 1]
        return months_en[month - 1]

    def _get_weekday_name(self, weekday: int, locale: str = 'pt_BR') -> str:
        """Get weekday name for locale."""
        weekdays_pt = [
            'Segunda-feira', 'Terça-feira', 'Quarta-feira', 'Quinta-feira',
            'Sexta-feira', 'Sábado', 'Domingo'
        ]
        weekdays_en = [
            'Monday', 'Tuesday', 'Wednesday', 'Thursday',
            'Friday', 'Saturday', 'Sunday'
        ]

        if locale.startswith('pt'):
            return weekdays_pt[weekday]
        return weekdays_en[weekday]


def create_globals_context(
    workflow: Optional[Dict] = None,
    execution: Optional[Dict] = None,
    custom: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Convenience function to create globals context.

    Args:
        workflow: Workflow metadata
        execution: Execution metadata
        custom: Custom variables

    Returns:
        Dictionary with '_globals' key containing all global variables
    """
    provider = GlobalVarsProvider(
        workflow_context=workflow,
        execution_context=execution,
        custom_vars=custom
    )

    return {
        '_globals': provider.get_all()
    }
