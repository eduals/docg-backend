"""
Steps Iterator - Processa steps sequencialmente.

Similar ao iterateSteps do Automatisch, processa:
1. Trigger step primeiro
2. Action steps em sequência
3. Cria ExecutionStep para cada step
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


async def iterate_steps(
    flow_context: Any,
    trigger_data: Dict[str, Any] = None,
    test_run: bool = False,
    resume_step_id: Optional[str] = None,
    resume_execution_id: Optional[str] = None,
    until_step: Optional[str] = None,
    skip_steps: Optional[List[str]] = None,
    mock_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Itera sobre todos os steps de um workflow.

    Args:
        flow_context: FlowContextData com workflow e nodes
        trigger_data: Dados do trigger
        test_run: Se True, não persiste execução
        resume_step_id: Step a partir do qual retomar
        resume_execution_id: Execução a retomar
        until_step: Para ANTES de executar este step (opcional)
        skip_steps: Lista de step_ids a pular (opcional)
        mock_data: Dict de {step_id: mock_output} para simular outputs (opcional)

    Returns:
        Dict com resultado da execução
    """
    from app.models import WorkflowExecution, WorkflowNode, ExecutionStep
    from app.database import db
    from app.engine.flow.context import (
        get_trigger_node,
        get_action_nodes,
        get_first_action_node,
        get_next_node,
        get_node_by_id,
    )
    from app.engine.trigger.context import build_trigger_context
    from app.engine.trigger.process import process_trigger_step
    from app.engine.action.context import build_action_context
    from app.engine.action.process import process_action_step

    # Criar ou retomar execução
    if resume_execution_id:
        execution = WorkflowExecution.query.get(resume_execution_id)
        if not execution:
            raise ValueError(f"Execution {resume_execution_id} not found")
    else:
        execution = WorkflowExecution(
            workflow_id=flow_context.workflow_id,
            trigger_data=trigger_data or {},
            status='running',
            started_at=datetime.utcnow(),
        )
        if not test_run:
            db.session.add(execution)
            db.session.commit()

    execution_id = str(execution.id) if execution.id else 'test'
    trigger_output = {}
    previous_steps = []

    try:
        # 1. Processar trigger node
        trigger_node_data = get_trigger_node(flow_context)
        if trigger_node_data:
            trigger_node = WorkflowNode.query.get(trigger_node_data['id'])
            if trigger_node:
                # Construir contexto do trigger
                trigger_context = await build_trigger_context(
                    node=trigger_node,
                    execution_id=execution_id,
                    flow_context=flow_context,
                    trigger_data=trigger_data,
                )

                # Criar ExecutionStep para trigger
                trigger_step = ExecutionStep.create_for_node(
                    execution_id=execution_id,
                    node=trigger_node,
                    data_in=trigger_data,
                )
                if not test_run:
                    db.session.add(trigger_step)
                    trigger_step.start()
                    db.session.commit()

                try:
                    # Processar trigger
                    trigger_output = await process_trigger_step(
                        node=trigger_node,
                        trigger_data=trigger_data,
                        context=trigger_context,
                    )

                    if not test_run:
                        trigger_step.complete(data_out=trigger_output)
                        db.session.commit()

                    previous_steps.append(trigger_step)

                except Exception as e:
                    logger.error(f"Trigger step failed: {e}")
                    if not test_run:
                        trigger_step.fail(str(e))
                        execution.status = 'failed'
                        execution.error_message = str(e)
                        db.session.commit()
                    raise

        # 2. Processar action nodes com suporte a branching
        last_action_output = {}

        # Determinar node inicial
        if resume_step_id:
            # Se retomando, começar do step especificado
            current_node_data = get_node_by_id(flow_context, resume_step_id)
            # Carregar steps anteriores já executados
            for node_data in get_action_nodes(flow_context):
                if node_data['id'] == resume_step_id:
                    break
                existing_step = ExecutionStep.query.filter_by(
                    execution_id=execution_id,
                    step_id=node_data['id'],
                    status='success',
                ).first()
                if existing_step:
                    previous_steps.append(existing_step)
        else:
            # Começar do primeiro action node
            current_node_data = get_first_action_node(flow_context)

        # Inicializar skip_steps como set para lookup O(1)
        skip_set = set(skip_steps or [])

        # Loop de execução com branching
        while current_node_data:
            node_id = current_node_data['id']

            # Verificar se deve parar antes deste step (until_step)
            if until_step and node_id == until_step:
                logger.info(f"Stopping before step {node_id} (until_step)")
                break

            action_node = WorkflowNode.query.get(node_id)
            if not action_node:
                logger.warning(f"Node {node_id} not found, skipping")
                break

            # Verificar se step deve ser pulado
            if node_id in skip_set:
                logger.info(f"Skipping node {action_node.position}: {action_node.node_type} ({node_id})")
                # Criar ExecutionStep marcado como skipped
                if not test_run:
                    skip_step = ExecutionStep.create_for_node(
                        execution_id=execution_id,
                        node=action_node,
                        data_in=action_node.config,
                    )
                    db.session.add(skip_step)
                    skip_step.status = 'skipped'
                    db.session.commit()
                # Determinar próximo e continuar
                current_node_data = get_next_node(
                    flow_context=flow_context,
                    current_node_id=node_id,
                    context={},
                    previous_steps=previous_steps,
                )
                continue

            logger.info(f"Executing node {action_node.position}: {action_node.node_type} ({node_id})")

            # Construir contexto da action
            action_context = await build_action_context(
                node=action_node,
                execution_id=execution_id,
                flow_context=flow_context,
                trigger_output=trigger_output,
                previous_steps=previous_steps,
            )

            # Criar ExecutionStep
            action_step = ExecutionStep.create_for_node(
                execution_id=execution_id,
                node=action_node,
                data_in=action_node.config,
            )
            if not test_run:
                db.session.add(action_step)
                action_step.start()

                # Atualizar current_node na execução
                execution.current_node_id = action_node.id
                db.session.commit()

            try:
                # Verificar se há mock_data para este step
                if mock_data and node_id in mock_data:
                    logger.info(f"Using mock data for node {node_id}")
                    action_output = mock_data[node_id]
                else:
                    # Processar action normalmente
                    action_output = await process_action_step(
                        node=action_node,
                        parameters=action_node.config,
                        context=action_context,
                        previous_steps=previous_steps,
                    )

                last_action_output = action_output

                if not test_run:
                    action_step.complete(data_out=action_output)
                    db.session.commit()

                previous_steps.append(action_step)

            except Exception as e:
                logger.error(f"Action step {action_node.id} failed: {e}")
                if not test_run:
                    action_step.fail(str(e))
                    execution.status = 'failed'
                    execution.error_message = str(e)
                    execution.completed_at = datetime.utcnow()
                    db.session.commit()
                raise

            # Determinar próximo node (branching ou sequencial)
            # Construir context para avaliação de condições
            branch_context = {
                'trigger': trigger_output,
                'execution': {'id': execution_id, 'test_run': test_run},
                'flow': flow_context.to_dict(),
            }
            # Adicionar outputs de steps anteriores
            for step in previous_steps:
                if hasattr(step, 'step_id') and hasattr(step, 'data_out'):
                    branch_context[f'step.{step.step_id}'] = step.data_out or {}

            current_node_data = get_next_node(
                flow_context=flow_context,
                current_node_id=node_id,
                context=branch_context,
                previous_steps=previous_steps,
            )

        # 3. Marcar execução como completa
        if not test_run:
            execution.status = 'completed'
            execution.completed_at = datetime.utcnow()
            execution.current_node_id = None
            if execution.started_at:
                execution.execution_time_ms = int(
                    (execution.completed_at - execution.started_at).total_seconds() * 1000
                )
            db.session.commit()

        return {
            'execution_id': execution_id,
            'status': 'completed',
            'trigger_output': trigger_output,
            'action_output': last_action_output,
            'steps_executed': len(previous_steps),
        }

    except Exception as e:
        logger.error(f"Workflow execution failed: {e}")
        raise


async def iterate_single_step(
    step_id: str,
    execution_id: str,
    flow_context: Any,
    trigger_output: Dict[str, Any] = None,
    previous_steps: List[Any] = None,
) -> Dict[str, Any]:
    """
    Executa um único step (usado pelo Temporal).

    Args:
        step_id: ID do WorkflowNode
        execution_id: ID da execução
        flow_context: FlowContextData
        trigger_output: Output do trigger
        previous_steps: Steps anteriores

    Returns:
        Dict com resultado do step
    """
    from app.models import WorkflowNode, ExecutionStep
    from app.database import db
    from app.engine.action.context import build_action_context
    from app.engine.action.process import process_action_step
    from app.engine.trigger.context import build_trigger_context
    from app.engine.trigger.process import process_trigger_step

    node = WorkflowNode.query.get(step_id)
    if not node:
        raise ValueError(f"Node {step_id} not found")

    if node.is_trigger():
        context = await build_trigger_context(
            node=node,
            execution_id=execution_id,
            flow_context=flow_context,
            trigger_data=trigger_output,
        )
        return await process_trigger_step(node, trigger_output, context)
    else:
        context = await build_action_context(
            node=node,
            execution_id=execution_id,
            flow_context=flow_context,
            trigger_output=trigger_output,
            previous_steps=previous_steps or [],
        )
        return await process_action_step(node, node.config, context, previous_steps or [])
