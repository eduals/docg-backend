"""
Tests for branching functionality in workflow execution.

FASE 1: Branching no iterate_steps
"""

import pytest
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from unittest.mock import Mock, patch, MagicMock


@dataclass
class MockFlowContext:
    """Mock FlowContextData for testing"""
    workflow_id: str = 'test-workflow-id'
    workflow_name: str = 'Test Workflow'
    organization_id: str = 'test-org-id'
    status: str = 'active'
    trigger_type: Optional[str] = None
    trigger_config: Optional[Dict[str, Any]] = None
    nodes: List[Dict[str, Any]] = field(default_factory=list)
    connections: Dict[str, Any] = field(default_factory=dict)
    templates: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return {
            'workflow_id': self.workflow_id,
            'workflow_name': self.workflow_name,
            'nodes': self.nodes,
        }


class TestGetFirstActionNode:
    """Tests for get_first_action_node()"""

    def test_returns_first_action_node(self):
        """Should return the first node with position > 1"""
        from app.engine.flow.context import get_first_action_node

        flow_context = MockFlowContext(nodes=[
            {'id': 'trigger', 'position': 1, 'node_type': 'hubspot'},
            {'id': 'action1', 'position': 2, 'node_type': 'google-docs'},
            {'id': 'action2', 'position': 3, 'node_type': 'gmail'},
        ])

        result = get_first_action_node(flow_context)
        assert result is not None
        assert result['id'] == 'action1'
        assert result['position'] == 2

    def test_returns_none_when_no_actions(self):
        """Should return None when only trigger exists"""
        from app.engine.flow.context import get_first_action_node

        flow_context = MockFlowContext(nodes=[
            {'id': 'trigger', 'position': 1, 'node_type': 'hubspot'},
        ])

        result = get_first_action_node(flow_context)
        assert result is None

    def test_returns_none_when_empty(self):
        """Should return None when no nodes"""
        from app.engine.flow.context import get_first_action_node

        flow_context = MockFlowContext(nodes=[])

        result = get_first_action_node(flow_context)
        assert result is None


class TestGetNextSequentialNode:
    """Tests for get_next_sequential_node()"""

    def test_returns_next_node(self):
        """Should return node with position + 1"""
        from app.engine.flow.context import get_next_sequential_node

        flow_context = MockFlowContext(nodes=[
            {'id': 'node1', 'position': 1},
            {'id': 'node2', 'position': 2},
            {'id': 'node3', 'position': 3},
        ])

        result = get_next_sequential_node(flow_context, 'node2')
        assert result is not None
        assert result['id'] == 'node3'

    def test_returns_none_for_last_node(self):
        """Should return None for the last node"""
        from app.engine.flow.context import get_next_sequential_node

        flow_context = MockFlowContext(nodes=[
            {'id': 'node1', 'position': 1},
            {'id': 'node2', 'position': 2},
        ])

        result = get_next_sequential_node(flow_context, 'node2')
        assert result is None

    def test_returns_none_for_unknown_node(self):
        """Should return None for unknown node ID"""
        from app.engine.flow.context import get_next_sequential_node

        flow_context = MockFlowContext(nodes=[
            {'id': 'node1', 'position': 1},
        ])

        result = get_next_sequential_node(flow_context, 'unknown')
        assert result is None


class TestGetNodeById:
    """Tests for get_node_by_id()"""

    def test_finds_existing_node(self):
        """Should find node by ID"""
        from app.engine.flow.context import get_node_by_id

        flow_context = MockFlowContext(nodes=[
            {'id': 'node1', 'position': 1},
            {'id': 'node2', 'position': 2},
        ])

        result = get_node_by_id(flow_context, 'node2')
        assert result is not None
        assert result['id'] == 'node2'

    def test_returns_none_for_unknown(self):
        """Should return None for unknown ID"""
        from app.engine.flow.context import get_node_by_id

        flow_context = MockFlowContext(nodes=[
            {'id': 'node1', 'position': 1},
        ])

        result = get_node_by_id(flow_context, 'unknown')
        assert result is None


class TestBranchConditionEvaluation:
    """Tests for branch condition evaluation in DocGWorkflow"""

    def test_compare_equals(self):
        """Test == operator"""
        from app.temporal.workflows.docg_workflow import DocGWorkflow

        workflow = DocGWorkflow()

        assert workflow._compare_values('hello', '==', 'hello') is True
        assert workflow._compare_values('hello', '==', 'world') is False
        assert workflow._compare_values(10, '==', '10') is True

    def test_compare_not_equals(self):
        """Test != operator"""
        from app.temporal.workflows.docg_workflow import DocGWorkflow

        workflow = DocGWorkflow()

        assert workflow._compare_values('hello', '!=', 'world') is True
        assert workflow._compare_values('hello', '!=', 'hello') is False

    def test_compare_greater_than(self):
        """Test > operator"""
        from app.temporal.workflows.docg_workflow import DocGWorkflow

        workflow = DocGWorkflow()

        assert workflow._compare_values(10, '>', 5) is True
        assert workflow._compare_values(5, '>', 10) is False
        assert workflow._compare_values('10', '>', '5') is True

    def test_compare_less_than(self):
        """Test < operator"""
        from app.temporal.workflows.docg_workflow import DocGWorkflow

        workflow = DocGWorkflow()

        assert workflow._compare_values(5, '<', 10) is True
        assert workflow._compare_values(10, '<', 5) is False

    def test_compare_greater_equal(self):
        """Test >= operator"""
        from app.temporal.workflows.docg_workflow import DocGWorkflow

        workflow = DocGWorkflow()

        assert workflow._compare_values(10, '>=', 10) is True
        assert workflow._compare_values(11, '>=', 10) is True
        assert workflow._compare_values(9, '>=', 10) is False

    def test_compare_less_equal(self):
        """Test <= operator"""
        from app.temporal.workflows.docg_workflow import DocGWorkflow

        workflow = DocGWorkflow()

        assert workflow._compare_values(10, '<=', 10) is True
        assert workflow._compare_values(9, '<=', 10) is True
        assert workflow._compare_values(11, '<=', 10) is False

    def test_compare_contains(self):
        """Test contains operator"""
        from app.temporal.workflows.docg_workflow import DocGWorkflow

        workflow = DocGWorkflow()

        assert workflow._compare_values('hello world', 'contains', 'world') is True
        assert workflow._compare_values('hello world', 'contains', 'foo') is False

    def test_compare_not_contains(self):
        """Test not_contains operator"""
        from app.temporal.workflows.docg_workflow import DocGWorkflow

        workflow = DocGWorkflow()

        assert workflow._compare_values('hello world', 'not_contains', 'foo') is True
        assert workflow._compare_values('hello world', 'not_contains', 'world') is False

    def test_compare_starts_with(self):
        """Test starts_with operator"""
        from app.temporal.workflows.docg_workflow import DocGWorkflow

        workflow = DocGWorkflow()

        assert workflow._compare_values('hello world', 'starts_with', 'hello') is True
        assert workflow._compare_values('hello world', 'starts_with', 'world') is False

    def test_compare_ends_with(self):
        """Test ends_with operator"""
        from app.temporal.workflows.docg_workflow import DocGWorkflow

        workflow = DocGWorkflow()

        assert workflow._compare_values('hello world', 'ends_with', 'world') is True
        assert workflow._compare_values('hello world', 'ends_with', 'hello') is False

    def test_compare_is_empty(self):
        """Test is_empty operator"""
        from app.temporal.workflows.docg_workflow import DocGWorkflow

        workflow = DocGWorkflow()

        assert workflow._compare_values('', 'is_empty', None) is True
        assert workflow._compare_values(None, 'is_empty', None) is True
        assert workflow._compare_values([], 'is_empty', None) is True
        assert workflow._compare_values('hello', 'is_empty', None) is False

    def test_compare_is_not_empty(self):
        """Test is_not_empty operator"""
        from app.temporal.workflows.docg_workflow import DocGWorkflow

        workflow = DocGWorkflow()

        assert workflow._compare_values('hello', 'is_not_empty', None) is True
        assert workflow._compare_values([1, 2], 'is_not_empty', None) is True
        assert workflow._compare_values('', 'is_not_empty', None) is False
        assert workflow._compare_values(None, 'is_not_empty', None) is False

    def test_compare_invalid_operator(self):
        """Unknown operator should return False"""
        from app.temporal.workflows.docg_workflow import DocGWorkflow

        workflow = DocGWorkflow()

        assert workflow._compare_values('a', 'unknown', 'b') is False


class TestGetNextNode:
    """Tests for _get_next_node() in DocGWorkflow"""

    def test_sequential_node(self):
        """Should return next node by position for non-branch"""
        from app.temporal.workflows.docg_workflow import DocGWorkflow

        workflow = DocGWorkflow()

        current_node = {'id': 'node2', 'position': 2, 'structural_type': 'single'}
        action_nodes = [
            {'id': 'node2', 'position': 2},
            {'id': 'node3', 'position': 3},
        ]
        nodes_by_id = {n['id']: n for n in action_nodes}

        result = workflow._get_next_node(
            current_node=current_node,
            action_nodes=action_nodes,
            nodes_by_id=nodes_by_id,
            executed_steps={}
        )

        assert result is not None
        assert result['id'] == 'node3'

    def test_last_node_returns_none(self):
        """Should return None for last node"""
        from app.temporal.workflows.docg_workflow import DocGWorkflow

        workflow = DocGWorkflow()

        current_node = {'id': 'node3', 'position': 3, 'structural_type': 'single'}
        action_nodes = [
            {'id': 'node2', 'position': 2},
            {'id': 'node3', 'position': 3},
        ]
        nodes_by_id = {n['id']: n for n in action_nodes}

        result = workflow._get_next_node(
            current_node=current_node,
            action_nodes=action_nodes,
            nodes_by_id=nodes_by_id,
            executed_steps={}
        )

        assert result is None


class TestBranchConditionsEvaluation:
    """Tests for _evaluate_branch_conditions()"""

    def test_and_conditions_all_true(self):
        """All AND conditions true should return True"""
        from app.temporal.workflows.docg_workflow import DocGWorkflow

        workflow = DocGWorkflow()
        workflow._source_data = {}

        conditions = {
            'type': 'and',
            'rules': [
                {'field': 'value1', 'operator': '==', 'value': 'value1'},
                {'field': 'value2', 'operator': '==', 'value': 'value2'},
            ]
        }

        result = workflow._evaluate_branch_conditions(conditions, {})
        assert result is True

    def test_and_conditions_one_false(self):
        """One false AND condition should return False"""
        from app.temporal.workflows.docg_workflow import DocGWorkflow

        workflow = DocGWorkflow()
        workflow._source_data = {}

        conditions = {
            'type': 'and',
            'rules': [
                {'field': 'value1', 'operator': '==', 'value': 'value1'},
                {'field': 'value1', 'operator': '==', 'value': 'different'},
            ]
        }

        result = workflow._evaluate_branch_conditions(conditions, {})
        assert result is False

    def test_or_conditions_one_true(self):
        """One true OR condition should return True"""
        from app.temporal.workflows.docg_workflow import DocGWorkflow

        workflow = DocGWorkflow()
        workflow._source_data = {}

        conditions = {
            'type': 'or',
            'rules': [
                {'field': 'value1', 'operator': '==', 'value': 'different'},
                {'field': 'value2', 'operator': '==', 'value': 'value2'},
            ]
        }

        result = workflow._evaluate_branch_conditions(conditions, {})
        assert result is True

    def test_or_conditions_all_false(self):
        """All false OR conditions should return False"""
        from app.temporal.workflows.docg_workflow import DocGWorkflow

        workflow = DocGWorkflow()
        workflow._source_data = {}

        conditions = {
            'type': 'or',
            'rules': [
                {'field': 'value1', 'operator': '==', 'value': 'nope'},
                {'field': 'value2', 'operator': '==', 'value': 'nope'},
            ]
        }

        result = workflow._evaluate_branch_conditions(conditions, {})
        assert result is False

    def test_empty_rules_returns_true(self):
        """Empty rules should return True"""
        from app.temporal.workflows.docg_workflow import DocGWorkflow

        workflow = DocGWorkflow()
        workflow._source_data = {}

        conditions = {'type': 'and', 'rules': []}

        result = workflow._evaluate_branch_conditions(conditions, {})
        assert result is True
