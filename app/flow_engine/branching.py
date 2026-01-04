"""
Branching Logic - Handle conditional branching in flows

Supports:
- Simple conditions (equals, not equals, contains, etc)
- Complex conditions (AND, OR)
- Multiple branches
"""

import logging
from typing import Dict, Any, Optional, List
from enum import Enum

from app.flow_engine.variable_resolver import VariableResolver

logger = logging.getLogger(__name__)


class ConditionOperator(str, Enum):
    """Condition operators for branching"""
    EQUALS = "EQUALS"
    NOT_EQUALS = "NOT_EQUALS"
    CONTAINS = "CONTAINS"
    NOT_CONTAINS = "NOT_CONTAINS"
    STARTS_WITH = "STARTS_WITH"
    ENDS_WITH = "ENDS_WITH"
    GREATER_THAN = "GREATER_THAN"
    LESS_THAN = "LESS_THAN"
    GREATER_OR_EQUAL = "GREATER_OR_EQUAL"
    LESS_OR_EQUAL = "LESS_OR_EQUAL"
    IS_EMPTY = "IS_EMPTY"
    IS_NOT_EMPTY = "IS_NOT_EMPTY"
    EXISTS = "EXISTS"
    NOT_EXISTS = "NOT_EXISTS"


class LogicalOperator(str, Enum):
    """Logical operators for combining conditions"""
    AND = "AND"
    OR = "OR"


class BranchingHandler:
    """
    Handles conditional branching logic in flows.

    Branch definition example:
    {
        "type": "BRANCH",
        "name": "checkAmount",
        "branches": [
            {
                "name": "High Value",
                "condition": {
                    "operator": "AND",
                    "conditions": [
                        {
                            "field": "{{trigger.deal.amount}}",
                            "operator": "GREATER_THAN",
                            "value": 10000
                        }
                    ]
                },
                "steps": [...]
            },
            {
                "name": "Default",
                "condition": null,  # Default branch
                "steps": [...]
            }
        ]
    }
    """

    def __init__(self, resolver: VariableResolver):
        """
        Initialize branching handler.

        Args:
            resolver: Variable resolver for evaluating conditions
        """
        self.resolver = resolver

    def evaluate_branch(self, branch_def: Dict[str, Any]) -> Optional[str]:
        """
        Evaluate which branch to take.

        Args:
            branch_def: Branch step definition

        Returns:
            Name of branch to take, or None if no match
        """
        branches = branch_def.get('branches', [])

        # Evaluate each branch
        for branch in branches:
            branch_name = branch.get('name')
            condition = branch.get('condition')

            # Default branch (no condition)
            if not condition:
                logger.info(f"Taking default branch: {branch_name}")
                return branch_name

            # Evaluate condition
            if self._evaluate_condition(condition):
                logger.info(f"Taking branch: {branch_name}")
                return branch_name

        # No matching branch
        logger.warning("No matching branch found")
        return None

    def _evaluate_condition(self, condition: Dict[str, Any]) -> bool:
        """
        Evaluate a condition.

        Args:
            condition: Condition definition

        Returns:
            True if condition matches
        """
        operator = condition.get('operator')

        # Complex condition (AND/OR)
        if operator in [LogicalOperator.AND.value, LogicalOperator.OR.value]:
            sub_conditions = condition.get('conditions', [])
            results = [self._evaluate_condition(c) for c in sub_conditions]

            if operator == LogicalOperator.AND.value:
                return all(results)
            else:  # OR
                return any(results)

        # Simple condition
        field = condition.get('field')
        operator = condition.get('operator')
        expected_value = condition.get('value')

        # Resolve field value
        actual_value = self.resolver.resolve(field)

        return self._check_condition(actual_value, operator, expected_value)

    def _check_condition(
        self,
        actual: Any,
        operator: str,
        expected: Any
    ) -> bool:
        """
        Check a simple condition.

        Args:
            actual: Actual value from flow data
            operator: Condition operator
            expected: Expected value

        Returns:
            True if condition matches
        """
        try:
            if operator == ConditionOperator.EQUALS.value:
                return actual == expected

            elif operator == ConditionOperator.NOT_EQUALS.value:
                return actual != expected

            elif operator == ConditionOperator.CONTAINS.value:
                return expected in str(actual)

            elif operator == ConditionOperator.NOT_CONTAINS.value:
                return expected not in str(actual)

            elif operator == ConditionOperator.STARTS_WITH.value:
                return str(actual).startswith(str(expected))

            elif operator == ConditionOperator.ENDS_WITH.value:
                return str(actual).endswith(str(expected))

            elif operator == ConditionOperator.GREATER_THAN.value:
                return float(actual) > float(expected)

            elif operator == ConditionOperator.LESS_THAN.value:
                return float(actual) < float(expected)

            elif operator == ConditionOperator.GREATER_OR_EQUAL.value:
                return float(actual) >= float(expected)

            elif operator == ConditionOperator.LESS_OR_EQUAL.value:
                return float(actual) <= float(expected)

            elif operator == ConditionOperator.IS_EMPTY.value:
                return not actual or actual == "" or actual == []

            elif operator == ConditionOperator.IS_NOT_EMPTY.value:
                return bool(actual) and actual != "" and actual != []

            elif operator == ConditionOperator.EXISTS.value:
                return actual is not None

            elif operator == ConditionOperator.NOT_EXISTS.value:
                return actual is None

            else:
                logger.warning(f"Unknown operator: {operator}")
                return False

        except (ValueError, TypeError) as e:
            logger.warning(f"Error evaluating condition: {e}")
            return False

    def get_branch_steps(
        self,
        branch_def: Dict[str, Any],
        branch_name: str
    ) -> List[Dict[str, Any]]:
        """
        Get steps for a specific branch.

        Args:
            branch_def: Branch step definition
            branch_name: Name of branch to get

        Returns:
            List of step definitions for the branch
        """
        branches = branch_def.get('branches', [])

        for branch in branches:
            if branch.get('name') == branch_name:
                return branch.get('steps', [])

        return []
