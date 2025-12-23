"""
Context Builder for the tag system.

Builds a unified context from various data sources for tag evaluation.
"""

from typing import Any, Dict, List, Optional
from app.tags.context.normalizer import get_normalizer_for_source, DataNormalizer
from app.tags.context.global_vars import GlobalVarsProvider


class ContextBuilder:
    """
    Builds evaluation context from various data sources.

    The context is a dictionary that the TagEvaluator uses to resolve variables.
    It combines:
    - Trigger data (normalized from source)
    - Step outputs from previous workflow steps
    - Flow/execution metadata
    - Global variables

    Structure:
    {
        'trigger': {...},           # Normalized trigger data
        'step': {                   # Previous step outputs by step_id
            'step_abc': {...},
            'step_xyz': {...}
        },
        'flow': {...},              # Flow metadata
        'execution': {...},         # Execution metadata
        'env': {...},               # Environment variables
        '_globals': {...},          # Global variables ($timestamp, etc)
        'locale': 'pt_BR'           # Locale for formatting
    }
    """

    def __init__(self, locale: str = 'pt_BR'):
        """
        Initialize the context builder.

        Args:
            locale: Default locale for formatting (default: pt_BR)
        """
        self.locale = locale
        self._normalizers: Dict[str, DataNormalizer] = {}

    def build(
        self,
        trigger_data: Optional[Dict[str, Any]] = None,
        trigger_source: str = 'generic',
        previous_steps: Optional[List[Dict[str, Any]]] = None,
        flow_context: Optional[Dict[str, Any]] = None,
        execution_context: Optional[Dict[str, Any]] = None,
        env_vars: Optional[Dict[str, str]] = None,
        custom_globals: Optional[Dict[str, Any]] = None,
        workflow_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Build a complete context for tag evaluation.

        Args:
            trigger_data: Raw data from the trigger (will be normalized)
            trigger_source: Source identifier for normalization (e.g., 'hubspot')
            previous_steps: List of ExecutionStep outputs [{step_id: ..., data_out: ...}]
            flow_context: Flow metadata
            execution_context: Execution metadata
            env_vars: Environment variables
            custom_globals: Custom global variables to add
            workflow_metadata: Workflow info (name, id)

        Returns:
            Complete context dictionary for TagEvaluator
        """
        context = {
            'locale': self.locale
        }

        # 1. Process trigger data
        if trigger_data:
            normalizer = get_normalizer_for_source(trigger_source)
            normalized_trigger = normalizer.normalize(trigger_data)
            context['trigger'] = normalized_trigger

            # Also expose at root level for backward compatibility
            for key, value in normalized_trigger.items():
                if not key.startswith('_') and key != 'associated':
                    context[key] = value

        # 2. Process previous steps
        context['step'] = {}
        if previous_steps:
            for step in previous_steps:
                step_id = step.get('step_id') or step.get('node_id') or step.get('id')
                data_out = step.get('data_out') or step.get('output') or {}

                if step_id:
                    context['step'][step_id] = data_out

                    # Also try to use action_key as alias
                    action_key = step.get('action_key')
                    if action_key:
                        context['step'][action_key] = data_out

        # 3. Add flow context
        if flow_context:
            context['flow'] = flow_context

        # 4. Add execution context
        if execution_context:
            context['execution'] = execution_context

        # 5. Add environment variables
        if env_vars:
            context['env'] = env_vars

        # 6. Add global variables
        globals_provider = GlobalVarsProvider(
            workflow_context=workflow_metadata or {},
            execution_context=execution_context or {},
            custom_vars=custom_globals or {}
        )
        context['_globals'] = globals_provider.get_all()

        return context

    def build_from_execution(
        self,
        execution,  # WorkflowExecution model instance
        workflow=None,  # Workflow model instance
        trigger_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Build context from a WorkflowExecution instance.

        This is a convenience method for use within the engine.

        Args:
            execution: WorkflowExecution model instance
            workflow: Workflow model instance (optional, will be fetched if not provided)
            trigger_data: Override trigger data (uses execution.trigger_data if not provided)

        Returns:
            Complete context dictionary
        """
        # Get workflow if not provided
        if workflow is None and execution.workflow_id:
            # Lazy import to avoid circular dependencies
            from app.models import Workflow
            workflow = Workflow.query.get(execution.workflow_id)

        # Get trigger data
        if trigger_data is None:
            trigger_data = execution.trigger_data or {}

        # Determine source from workflow trigger
        trigger_source = 'generic'
        if workflow and workflow.nodes:
            trigger_node = next(
                (n for n in workflow.nodes if n.get('type') == 'trigger'),
                None
            )
            if trigger_node:
                app_key = trigger_node.get('data', {}).get('app_key', '')
                if 'hubspot' in app_key.lower():
                    trigger_source = 'hubspot'
                elif 'google_forms' in app_key.lower() or 'forms' in app_key.lower():
                    trigger_source = 'google_forms'
                elif 'stripe' in app_key.lower():
                    trigger_source = 'stripe'
                elif 'webhook' in app_key.lower():
                    trigger_source = 'webhook'

        # Get previous steps
        previous_steps = []
        if execution.steps:
            for step in execution.steps:
                if step.status == 'success' and step.data_out:
                    previous_steps.append({
                        'step_id': step.node_id,
                        'action_key': step.action_key,
                        'data_out': step.data_out
                    })

        # Build workflow metadata
        workflow_metadata = {}
        if workflow:
            workflow_metadata = {
                'id': str(workflow.id),
                'name': workflow.name,
            }

        # Build execution context
        execution_context = {
            'id': str(execution.id),
            'started_at': execution.started_at.isoformat() if execution.started_at else None,
            'correlation_id': str(execution.correlation_id) if execution.correlation_id else None,
        }

        return self.build(
            trigger_data=trigger_data,
            trigger_source=trigger_source,
            previous_steps=previous_steps,
            execution_context=execution_context,
            workflow_metadata=workflow_metadata
        )

    def add_step_output(
        self,
        context: Dict[str, Any],
        step_id: str,
        output: Dict[str, Any],
        action_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Add a step output to an existing context.

        This is useful for updating context during workflow execution.

        Args:
            context: Existing context dictionary
            step_id: Step ID
            output: Step output data
            action_key: Optional action key as alias

        Returns:
            Updated context (same dict, modified in place)
        """
        if 'step' not in context:
            context['step'] = {}

        context['step'][step_id] = output

        if action_key:
            context['step'][action_key] = output

        return context

    def merge_contexts(self, *contexts) -> Dict[str, Any]:
        """
        Merge multiple contexts into one.

        Later contexts override earlier ones.

        Args:
            *contexts: Context dictionaries to merge

        Returns:
            Merged context
        """
        result = {'locale': self.locale}

        for ctx in contexts:
            if ctx:
                for key, value in ctx.items():
                    if key == 'step' and 'step' in result:
                        # Merge step outputs
                        result['step'].update(value)
                    elif key == '_globals' and '_globals' in result:
                        # Merge globals
                        result['_globals'].update(value)
                    elif key == 'env' and 'env' in result:
                        # Merge env vars
                        result['env'].update(value)
                    else:
                        result[key] = value

        return result
