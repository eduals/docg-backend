"""
Engine Integration - Conecta Engine com o sistema existente.

Este módulo fornece funções de integração para conectar a nova
Engine com o código existente (activities, routes, services).
"""

from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


async def execute_workflow_step(
    execution_id: str,
    step_id: str,
    trigger_output: Dict[str, Any] = None,
    previous_steps: list = None,
) -> Dict[str, Any]:
    """
    Executa um step de workflow usando a nova Engine.

    Esta função serve como ponte entre as activities do Temporal
    e a nova Engine.

    Args:
        execution_id: ID da execução
        step_id: ID do node/step
        trigger_output: Output do trigger
        previous_steps: Steps anteriores

    Returns:
        Dict com resultado da execução
    """
    from app.engine.steps.iterate import iterate_single_step
    from app.engine.flow.context import build_flow_context
    from app.models import WorkflowExecution

    execution = WorkflowExecution.query.get(execution_id)
    if not execution:
        raise ValueError(f"Execution {execution_id} not found")

    flow_context = build_flow_context(str(execution.workflow_id))

    return await iterate_single_step(
        step_id=step_id,
        execution_id=execution_id,
        flow_context=flow_context,
        trigger_output=trigger_output,
        previous_steps=previous_steps,
    )


async def run_workflow_via_engine(
    workflow_id: str,
    trigger_data: Dict[str, Any] = None,
    test_run: bool = False,
) -> Dict[str, Any]:
    """
    Executa um workflow completo usando a nova Engine.

    Args:
        workflow_id: ID do workflow
        trigger_data: Dados do trigger
        test_run: Se True, não persiste

    Returns:
        Dict com resultado
    """
    from app.engine import Engine

    engine = Engine()
    return await engine.run(
        workflow_id=workflow_id,
        trigger_data=trigger_data,
        test_run=test_run,
    )


def get_app_for_action(node_type: str):
    """
    Retorna o App registrado para um tipo de node.

    Args:
        node_type: Tipo do node (ex: 'google-docs', 'gmail')

    Returns:
        BaseApp ou None
    """
    from app.apps import AppRegistry
    return AppRegistry.get_by_node_type(node_type)


def compute_step_parameters(
    parameters: Dict[str, Any],
    execution_id: str,
    trigger_output: Dict[str, Any] = None,
    previous_steps: list = None,
) -> Dict[str, Any]:
    """
    Aplica substituição de variáveis nos parâmetros.

    Args:
        parameters: Parâmetros originais
        execution_id: ID da execução
        trigger_output: Output do trigger
        previous_steps: Steps anteriores

    Returns:
        Parâmetros com variáveis substituídas
    """
    from app.engine.compute_parameters import compute_parameters
    return compute_parameters(
        parameters=parameters,
        execution_id=execution_id,
        trigger_output=trigger_output,
        previous_steps=previous_steps,
    )


# Re-exports para facilitar imports
from app.engine.global_variable import GlobalVariable, AuthContext, FlowContext, StepContext
from app.engine.compute_parameters import compute_parameters, extract_variables
from app.engine.flow.context import build_flow_context, FlowContextData

__all__ = [
    'execute_workflow_step',
    'run_workflow_via_engine',
    'get_app_for_action',
    'compute_step_parameters',
    # Re-exports
    'GlobalVariable',
    'AuthContext',
    'FlowContext',
    'StepContext',
    'compute_parameters',
    'extract_variables',
    'build_flow_context',
    'FlowContextData',
]
