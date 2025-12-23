"""
Pytest fixtures for engine tests
"""

import pytest
from unittest.mock import MagicMock, patch
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import uuid


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
            'organization_id': self.organization_id,
            'status': self.status,
            'nodes': self.nodes,
        }


@pytest.fixture
def mock_flow_context():
    """Create a mock flow context"""
    return MockFlowContext()


@pytest.fixture
def mock_flow_context_with_nodes():
    """Create a mock flow context with sample nodes"""
    return MockFlowContext(
        nodes=[
            {
                'id': 'trigger-1',
                'position': 1,
                'node_type': 'hubspot',
                'structural_type': 'single',
                'config': {}
            },
            {
                'id': 'action-1',
                'position': 2,
                'node_type': 'google-docs',
                'structural_type': 'single',
                'config': {}
            },
            {
                'id': 'action-2',
                'position': 3,
                'node_type': 'gmail',
                'structural_type': 'single',
                'config': {}
            },
        ]
    )


@pytest.fixture
def mock_flow_context_with_branch():
    """Create a mock flow context with branching node"""
    return MockFlowContext(
        nodes=[
            {
                'id': 'trigger-1',
                'position': 1,
                'node_type': 'hubspot',
                'structural_type': 'single',
            },
            {
                'id': 'branch-1',
                'position': 2,
                'node_type': 'branch',
                'structural_type': 'branch',
                'branch_conditions': [
                    {
                        'name': 'High Value',
                        'conditions': {
                            'type': 'and',
                            'rules': [
                                {'field': '{{step.trigger.amount}}', 'operator': '>', 'value': 10000}
                            ]
                        },
                        'next_node_id': 'high-value-action'
                    },
                    {
                        'name': 'Default',
                        'conditions': None,
                        'next_node_id': 'default-action'
                    }
                ]
            },
            {
                'id': 'high-value-action',
                'position': 3,
                'node_type': 'gmail',
                'structural_type': 'single',
            },
            {
                'id': 'default-action',
                'position': 4,
                'node_type': 'gmail',
                'structural_type': 'single',
            },
        ]
    )


@pytest.fixture
def mock_db_session():
    """Mock database session"""
    with patch('app.database.db') as mock_db:
        mock_db.session = MagicMock()
        yield mock_db


@pytest.fixture
def mock_workflow_node():
    """Create a mock WorkflowNode"""
    node = MagicMock()
    node.id = uuid.uuid4()
    node.position = 2
    node.node_type = 'google-docs'
    node.structural_type = 'single'
    node.config = {}
    node.is_branch.return_value = False
    node.is_trigger.return_value = False
    return node


@pytest.fixture
def mock_workflow_execution():
    """Create a mock WorkflowExecution"""
    execution = MagicMock()
    execution.id = uuid.uuid4()
    execution.workflow_id = uuid.uuid4()
    execution.status = 'running'
    execution.version = 1
    execution.trigger_data = {}
    return execution


@pytest.fixture
def mock_execution_step():
    """Create a mock ExecutionStep"""
    step = MagicMock()
    step.id = uuid.uuid4()
    step.step_id = str(uuid.uuid4())
    step.status = 'pending'
    step.data_in = {}
    step.data_out = {}
    return step


@pytest.fixture
def sample_action_arguments():
    """Create sample ActionArguments for testing"""
    from app.apps.base import ActionArgument, ArgumentType

    return [
        ActionArgument(
            key='email',
            label='Email',
            type=ArgumentType.STRING,
            required=True,
            pattern=r'^[\w\.-]+@[\w\.-]+\.\w+$'
        ),
        ActionArgument(
            key='amount',
            label='Amount',
            type=ArgumentType.NUMBER,
            min_value=0,
            max_value=1000000
        ),
        ActionArgument(
            key='active',
            label='Active',
            type=ArgumentType.BOOLEAN
        ),
        ActionArgument(
            key='notes',
            label='Notes',
            type=ArgumentType.STRING,
            max_length=500
        ),
    ]
