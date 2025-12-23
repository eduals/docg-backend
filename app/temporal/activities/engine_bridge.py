"""
Engine Bridge - Ponte entre Activities e a nova Engine.

Este módulo fornece funções auxiliares para as activities
utilizarem os novos componentes da Engine (Apps, ExecutionStep, etc).
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


def create_execution_step(
    execution_id: str,
    step_id: str,
    step_type: str,
    position: int,
    data_in: Dict[str, Any] = None
) -> Optional[str]:
    """
    Cria um ExecutionStep para rastrear execução de um node.

    Args:
        execution_id: ID da WorkflowExecution
        step_id: ID do WorkflowNode
        step_type: Tipo do node (google-docs, gmail, etc)
        position: Posição do node no workflow
        data_in: Dados de entrada do step

    Returns:
        ID do ExecutionStep criado ou None se falhar
    """
    try:
        from app.models import ExecutionStep
        from app.database import db

        step = ExecutionStep(
            execution_id=execution_id,
            step_id=step_id,
            step_type=step_type,
            position=position,
            data_in=data_in,
            status='pending'
        )
        db.session.add(step)
        db.session.commit()

        logger.info(f"ExecutionStep criado: {step.id} para node {step_id}")
        return str(step.id)

    except Exception as e:
        logger.warning(f"Falha ao criar ExecutionStep: {e}")
        return None


def start_execution_step(execution_step_id: str) -> bool:
    """
    Marca ExecutionStep como iniciado.

    Args:
        execution_step_id: ID do ExecutionStep

    Returns:
        True se sucesso
    """
    try:
        from app.models import ExecutionStep
        from app.database import db

        step = ExecutionStep.query.get(execution_step_id)
        if step:
            step.start()
            db.session.commit()
            return True
        return False

    except Exception as e:
        logger.warning(f"Falha ao iniciar ExecutionStep: {e}")
        return False


def complete_execution_step(
    execution_step_id: str,
    data_out: Dict[str, Any] = None
) -> bool:
    """
    Marca ExecutionStep como completo.

    Args:
        execution_step_id: ID do ExecutionStep
        data_out: Dados de saída do step

    Returns:
        True se sucesso
    """
    try:
        from app.models import ExecutionStep
        from app.database import db

        step = ExecutionStep.query.get(execution_step_id)
        if step:
            step.complete(data_out=data_out)
            db.session.commit()
            return True
        return False

    except Exception as e:
        logger.warning(f"Falha ao completar ExecutionStep: {e}")
        return False


def fail_execution_step(
    execution_step_id: str,
    error_message: str,
    error_details: Dict[str, Any] = None
) -> bool:
    """
    Marca ExecutionStep como falho.

    Args:
        execution_step_id: ID do ExecutionStep
        error_message: Mensagem de erro
        error_details: Detalhes adicionais do erro

    Returns:
        True se sucesso
    """
    try:
        from app.models import ExecutionStep
        from app.database import db

        step = ExecutionStep.query.get(execution_step_id)
        if step:
            step.fail(error_message=error_message, error_details=error_details)
            db.session.commit()
            return True
        return False

    except Exception as e:
        logger.warning(f"Falha ao marcar ExecutionStep como falho: {e}")
        return False


def get_previous_steps_output(execution_id: str) -> List[Dict[str, Any]]:
    """
    Obtém outputs dos steps anteriores de uma execução.

    Args:
        execution_id: ID da WorkflowExecution

    Returns:
        Lista de dicts com step_id, step_type e data_out
    """
    try:
        from app.models import ExecutionStep

        steps = ExecutionStep.query.filter_by(
            execution_id=execution_id,
            status='success'
        ).order_by(ExecutionStep.position).all()

        return [
            {
                'step_id': str(step.step_id),
                'step_type': step.step_type,
                'position': step.position,
                'data_out': step.data_out
            }
            for step in steps
        ]

    except Exception as e:
        logger.warning(f"Falha ao obter steps anteriores: {e}")
        return []


def apply_compute_parameters(
    parameters: Dict[str, Any],
    execution_id: str,
    trigger_output: Dict[str, Any] = None,
    previous_steps: List[Any] = None
) -> Dict[str, Any]:
    """
    Aplica substituição de variáveis nos parâmetros.

    Args:
        parameters: Parâmetros com possíveis {{variáveis}}
        execution_id: ID da execução
        trigger_output: Output do trigger
        previous_steps: Steps anteriores (ExecutionSteps ou dicts)

    Returns:
        Parâmetros com variáveis substituídas
    """
    try:
        from app.engine.compute_parameters import compute_parameters

        return compute_parameters(
            parameters=parameters,
            execution_id=execution_id,
            trigger_output=trigger_output,
            previous_steps=previous_steps
        )

    except Exception as e:
        logger.warning(f"Falha ao aplicar compute_parameters: {e}")
        return parameters


def get_app_for_node(node_type: str):
    """
    Obtém App registrado para um tipo de node.

    Args:
        node_type: Tipo do node (google-docs, gmail, etc)

    Returns:
        BaseApp instance ou None
    """
    try:
        from app.apps import AppRegistry
        return AppRegistry.get_by_node_type(node_type)
    except Exception as e:
        logger.warning(f"Falha ao obter App para {node_type}: {e}")
        return None


async def execute_via_app(
    node_type: str,
    action_key: str,
    connection_id: str,
    parameters: Dict[str, Any],
    context: Any = None
) -> Dict[str, Any]:
    """
    Executa uma action usando o App registrado.

    Args:
        node_type: Tipo do node
        action_key: Chave da action
        connection_id: ID da conexão
        parameters: Parâmetros da action
        context: GlobalVariable context (opcional)

    Returns:
        Resultado da action
    """
    app = get_app_for_node(node_type)
    if not app:
        raise ValueError(f"App não encontrado para node_type: {node_type}")

    return await app.execute_action(
        action_key=action_key,
        connection_id=connection_id,
        parameters=parameters,
        context=context
    )


def build_global_variable_context(
    execution_id: str,
    node_id: str,
    trigger_output: Dict[str, Any] = None,
    previous_steps: List[Any] = None
) -> Any:
    """
    Constrói GlobalVariable context para um step.

    Args:
        execution_id: ID da execução
        node_id: ID do node
        trigger_output: Output do trigger
        previous_steps: Steps anteriores

    Returns:
        GlobalVariable configurado
    """
    try:
        from app.engine.action.context import build_action_context
        from app.engine.flow.context import build_flow_context
        from app.models import WorkflowExecution, WorkflowNode

        execution = WorkflowExecution.query.get(execution_id)
        if not execution:
            return None

        node = WorkflowNode.query.get(node_id)
        if not node:
            return None

        flow_context = build_flow_context(str(execution.workflow_id))

        # build_action_context é async, então retornar coroutine
        import asyncio
        return asyncio.run(build_action_context(
            node=node,
            execution_id=execution_id,
            flow_context=flow_context,
            trigger_output=trigger_output,
            previous_steps=previous_steps or []
        ))

    except Exception as e:
        logger.warning(f"Falha ao construir GlobalVariable: {e}")
        return None


# Activity decorator helper
def with_execution_step(func):
    """
    Decorator que automaticamente cria e gerencia ExecutionStep.

    Uso:
        @activity.defn
        @with_execution_step
        async def my_activity(data: Dict) -> Dict:
            ...
    """
    import functools

    @functools.wraps(func)
    async def wrapper(data: Dict[str, Any]) -> Dict[str, Any]:
        node = data.get('node', {})
        execution_id = data.get('execution_id')

        # Criar ExecutionStep
        step_id = create_execution_step(
            execution_id=execution_id,
            step_id=node.get('id'),
            step_type=node.get('node_type'),
            position=node.get('position', 0),
            data_in=data
        )

        if step_id:
            start_execution_step(step_id)

        try:
            # Executar activity original
            result = await func(data)

            # Marcar como completo
            if step_id:
                complete_execution_step(step_id, data_out=result)

            return result

        except Exception as e:
            # Marcar como falho
            if step_id:
                fail_execution_step(
                    step_id,
                    error_message=str(e),
                    error_details={'type': type(e).__name__}
                )
            raise

    return wrapper
