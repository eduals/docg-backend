"""
Tests for app/engine/engine.py

FASE 5: Test Run Granular
FASE 6: Optimistic Locking
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime
import uuid


class TestEngineRunParameters:
    """Tests for Engine.run() parameters"""

    def test_run_has_until_step_parameter(self):
        """Engine.run should accept until_step parameter"""
        from app.engine.engine import Engine
        import inspect

        sig = inspect.signature(Engine.run)
        params = list(sig.parameters.keys())

        assert 'until_step' in params

    def test_run_has_skip_steps_parameter(self):
        """Engine.run should accept skip_steps parameter"""
        from app.engine.engine import Engine
        import inspect

        sig = inspect.signature(Engine.run)
        params = list(sig.parameters.keys())

        assert 'skip_steps' in params

    def test_run_has_mock_data_parameter(self):
        """Engine.run should accept mock_data parameter"""
        from app.engine.engine import Engine
        import inspect

        sig = inspect.signature(Engine.run)
        params = list(sig.parameters.keys())

        assert 'mock_data' in params


class TestConcurrentExecutionError:
    """Tests for ConcurrentExecutionError"""

    def test_error_message(self):
        """Should format error message correctly"""
        from app.models.execution import ConcurrentExecutionError

        error = ConcurrentExecutionError(
            workflow_id='wf-123',
            execution_id='exec-456'
        )

        assert 'wf-123' in str(error)
        assert 'exec-456' in str(error)
        assert 'already running' in str(error)

    def test_error_without_execution_id(self):
        """Should work without execution_id"""
        from app.models.execution import ConcurrentExecutionError

        error = ConcurrentExecutionError(workflow_id='wf-123')

        assert 'wf-123' in str(error)
        assert error.execution_id is None

    def test_error_stores_ids(self):
        """Should store workflow_id and execution_id"""
        from app.models.execution import ConcurrentExecutionError

        error = ConcurrentExecutionError(
            workflow_id='wf-123',
            execution_id='exec-456'
        )

        assert error.workflow_id == 'wf-123'
        assert error.execution_id == 'exec-456'


class TestCheckConcurrentExecution:
    """Tests for WorkflowExecution.check_concurrent_execution()"""

    @patch('app.models.execution.WorkflowExecution.query')
    def test_no_concurrent_execution(self, mock_query):
        """Should not raise when no running execution exists"""
        from app.models.execution import WorkflowExecution

        mock_query.filter_by.return_value.first.return_value = None

        # Should not raise
        WorkflowExecution.check_concurrent_execution('wf-123')

    @patch('app.models.execution.WorkflowExecution.query')
    def test_concurrent_execution_exists(self, mock_query):
        """Should raise when running execution exists"""
        from app.models.execution import WorkflowExecution, ConcurrentExecutionError

        mock_execution = MagicMock()
        mock_execution.id = uuid.uuid4()
        mock_query.filter_by.return_value.first.return_value = mock_execution

        with pytest.raises(ConcurrentExecutionError):
            WorkflowExecution.check_concurrent_execution('wf-123')


class TestGetRunningExecution:
    """Tests for WorkflowExecution.get_running_execution()"""

    @patch('app.models.execution.WorkflowExecution.query')
    def test_returns_running_execution(self, mock_query):
        """Should return running execution when exists"""
        from app.models.execution import WorkflowExecution

        mock_execution = MagicMock()
        mock_execution.status = 'running'
        mock_query.filter_by.return_value.first.return_value = mock_execution

        result = WorkflowExecution.get_running_execution('wf-123')

        assert result == mock_execution
        mock_query.filter_by.assert_called_with(
            workflow_id='wf-123',
            status='running'
        )

    @patch('app.models.execution.WorkflowExecution.query')
    def test_returns_none_when_not_running(self, mock_query):
        """Should return None when no running execution"""
        from app.models.execution import WorkflowExecution

        mock_query.filter_by.return_value.first.return_value = None

        result = WorkflowExecution.get_running_execution('wf-123')

        assert result is None


class TestIterateStepsTestRunGranular:
    """Tests for iterate_steps with test run granular parameters"""

    def test_iterate_steps_has_until_step(self):
        """iterate_steps should accept until_step parameter"""
        from app.engine.steps.iterate import iterate_steps
        import inspect

        sig = inspect.signature(iterate_steps)
        params = list(sig.parameters.keys())

        assert 'until_step' in params

    def test_iterate_steps_has_skip_steps(self):
        """iterate_steps should accept skip_steps parameter"""
        from app.engine.steps.iterate import iterate_steps
        import inspect

        sig = inspect.signature(iterate_steps)
        params = list(sig.parameters.keys())

        assert 'skip_steps' in params

    def test_iterate_steps_has_mock_data(self):
        """iterate_steps should accept mock_data parameter"""
        from app.engine.steps.iterate import iterate_steps
        import inspect

        sig = inspect.signature(iterate_steps)
        params = list(sig.parameters.keys())

        assert 'mock_data' in params


class TestWorkflowExecutionVersion:
    """Tests for WorkflowExecution version column"""

    def test_has_version_column(self):
        """WorkflowExecution should have version column"""
        from app.models.execution import WorkflowExecution

        # Check if version column exists in model
        assert hasattr(WorkflowExecution, 'version')


class TestEngineRunConcurrencyCheck:
    """Tests for concurrent execution check in Engine.run()"""

    @pytest.mark.asyncio
    @patch('app.engine.engine.build_flow_context')
    @patch('app.models.WorkflowExecution.check_concurrent_execution')
    async def test_checks_concurrent_on_new_execution(
        self,
        mock_check,
        mock_build_context
    ):
        """Should check for concurrent execution when not resuming"""
        from app.engine.engine import Engine

        mock_build_context.return_value = AsyncMock()

        # Mock to prevent actual execution
        with patch('app.temporal.service.is_temporal_enabled', return_value=False):
            with patch('app.engine.steps.iterate.iterate_steps', new_callable=AsyncMock):
                try:
                    await Engine.run(
                        workflow_id='wf-123',
                        test_run=True
                    )
                except Exception:
                    pass  # We're just testing the check was called

        mock_check.assert_called_once_with('wf-123')

    @pytest.mark.asyncio
    @patch('app.engine.engine.build_flow_context')
    @patch('app.models.WorkflowExecution.check_concurrent_execution')
    async def test_skips_check_when_resuming(
        self,
        mock_check,
        mock_build_context
    ):
        """Should skip concurrent check when resuming"""
        from app.engine.engine import Engine

        mock_build_context.return_value = AsyncMock()

        with patch('app.temporal.service.is_temporal_enabled', return_value=False):
            with patch('app.engine.steps.iterate.iterate_steps', new_callable=AsyncMock):
                try:
                    await Engine.run(
                        workflow_id='wf-123',
                        resume_execution_id='exec-456',
                        test_run=True
                    )
                except Exception:
                    pass

        mock_check.assert_not_called()
