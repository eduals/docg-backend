"""
Tests for BranchingHandler
"""

import pytest
from app.flow_engine.branching import BranchingHandler
from app.flow_engine.variable_resolver import VariableResolver


class TestBranchingHandler:
    """Test branching logic"""

    def test_simple_equals_condition(self):
        """Test simple EQUALS condition"""
        resolver = VariableResolver(trigger_output={'status': 'active'})
        handler = BranchingHandler(resolver)

        condition = {
            'field': '{{trigger.status}}',
            'operator': 'EQUALS',
            'value': 'active'
        }

        result = handler._evaluate_condition(condition)
        assert result is True

    def test_greater_than_condition(self):
        """Test GREATER_THAN condition"""
        resolver = VariableResolver(trigger_output={'amount': 10000})
        handler = BranchingHandler(resolver)

        condition = {
            'field': '{{trigger.amount}}',
            'operator': 'GREATER_THAN',
            'value': 5000
        }

        result = handler._evaluate_condition(condition)
        assert result is True

    def test_contains_condition(self):
        """Test CONTAINS condition"""
        resolver = VariableResolver(trigger_output={'email': 'john@example.com'})
        handler = BranchingHandler(resolver)

        condition = {
            'field': '{{trigger.email}}',
            'operator': 'CONTAINS',
            'value': '@example.com'
        }

        result = handler._evaluate_condition(condition)
        assert result is True

    def test_and_condition(self):
        """Test AND logical operator"""
        resolver = VariableResolver(trigger_output={'amount': 10000, 'status': 'active'})
        handler = BranchingHandler(resolver)

        condition = {
            'operator': 'AND',
            'conditions': [
                {'field': '{{trigger.amount}}', 'operator': 'GREATER_THAN', 'value': 5000},
                {'field': '{{trigger.status}}', 'operator': 'EQUALS', 'value': 'active'}
            ]
        }

        result = handler._evaluate_condition(condition)
        assert result is True

    def test_or_condition(self):
        """Test OR logical operator"""
        resolver = VariableResolver(trigger_output={'amount': 1000, 'vip': True})
        handler = BranchingHandler(resolver)

        condition = {
            'operator': 'OR',
            'conditions': [
                {'field': '{{trigger.amount}}', 'operator': 'GREATER_THAN', 'value': 10000},
                {'field': '{{trigger.vip}}', 'operator': 'EQUALS', 'value': True}
            ]
        }

        result = handler._evaluate_condition(condition)
        assert result is True  # Second condition is true

    def test_evaluate_branch(self):
        """Test evaluating which branch to take"""
        resolver = VariableResolver(trigger_output={'amount': 15000})
        handler = BranchingHandler(resolver)

        branch_def = {
            'branches': [
                {
                    'name': 'High Value',
                    'condition': {
                        'field': '{{trigger.amount}}',
                        'operator': 'GREATER_THAN',
                        'value': 10000
                    }
                },
                {
                    'name': 'Low Value',
                    'condition': {
                        'field': '{{trigger.amount}}',
                        'operator': 'LESS_THAN',
                        'value': 10000
                    }
                },
                {
                    'name': 'Default',
                    'condition': None
                }
            ]
        }

        result = handler.evaluate_branch(branch_def)
        assert result == 'High Value'

    def test_default_branch(self):
        """Test taking default branch when no conditions match"""
        resolver = VariableResolver(trigger_output={'amount': 5000})
        handler = BranchingHandler(resolver)

        branch_def = {
            'branches': [
                {
                    'name': 'High Value',
                    'condition': {
                        'field': '{{trigger.amount}}',
                        'operator': 'GREATER_THAN',
                        'value': 10000
                    }
                },
                {
                    'name': 'Default',
                    'condition': None
                }
            ]
        }

        result = handler.evaluate_branch(branch_def)
        assert result == 'Default'

    def test_is_empty_condition(self):
        """Test IS_EMPTY condition"""
        resolver = VariableResolver(trigger_output={'notes': ''})
        handler = BranchingHandler(resolver)

        condition = {
            'field': '{{trigger.notes}}',
            'operator': 'IS_EMPTY',
            'value': None
        }

        result = handler._evaluate_condition(condition)
        assert result is True

    def test_exists_condition(self):
        """Test EXISTS condition"""
        resolver = VariableResolver(trigger_output={'name': 'John'})
        handler = BranchingHandler(resolver)

        condition = {
            'field': '{{trigger.name}}',
            'operator': 'EXISTS',
            'value': None
        }

        result = handler._evaluate_condition(condition)
        assert result is True

    def test_get_branch_steps(self):
        """Test getting steps for a specific branch"""
        resolver = VariableResolver(trigger_output={})
        handler = BranchingHandler(resolver)

        branch_def = {
            'branches': [
                {
                    'name': 'Branch A',
                    'steps': [{'type': 'ACTION', 'name': 'step1'}]
                },
                {
                    'name': 'Branch B',
                    'steps': [{'type': 'ACTION', 'name': 'step2'}]
                }
            ]
        }

        steps = handler.get_branch_steps(branch_def, 'Branch B')
        assert len(steps) == 1
        assert steps[0]['name'] == 'step2'
