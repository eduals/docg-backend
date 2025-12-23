"""
Engine Principal - Orquestrador central de execução de workflows.

Similar ao Engine do Automatisch, esta classe é responsável por:
- Decidir se executa via Temporal ou síncrono
- Coordenar a execução de steps
- Integrar com AppRegistry para resolver apps
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class Engine:
    """
    Engine centralizada para execução de workflows.

    Responsabilidades:
    - Carregar workflow e nodes
    - Decidir modo de execução (Temporal/síncrono)
    - Coordenar execução de steps
    - Gerenciar contexto entre steps
    """

    @staticmethod
    async def run(
        workflow_id: str,
        trigger_data: Optional[Dict[str, Any]] = None,
        test_run: bool = False,
        resume_step_id: Optional[str] = None,
        resume_execution_id: Optional[str] = None,
        until_step: Optional[str] = None,
        skip_steps: Optional[List[str]] = None,
        mock_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Executa um workflow.

        Se Temporal estiver habilitado (e não for test_run), inicia via Temporal.
        Caso contrário, executa de forma síncrona.

        Args:
            workflow_id: ID do workflow a executar
            trigger_data: Dados do trigger (webhook payload, etc)
            test_run: Se True, executa síncronamente para teste
            resume_step_id: Step a partir do qual retomar (opcional)
            resume_execution_id: ID de execução a retomar (opcional)
            until_step: Para a execução ANTES deste step (opcional)
            skip_steps: Lista de step_ids a pular (opcional)
            mock_data: Dict de {step_id: mock_output} para simular outputs (opcional)

        Returns:
            Dict com resultado da execução
        """
        from app.engine.flow.context import build_flow_context
        from app.engine.steps.iterate import iterate_steps
        from app.temporal.service import start_workflow_execution, is_temporal_enabled
        from app.models import WorkflowExecution

        # Check for concurrent executions (unless resuming)
        if not resume_execution_id:
            WorkflowExecution.check_concurrent_execution(workflow_id)

        # Build flow context
        flow_context = await build_flow_context(workflow_id)

        # Se Temporal habilitado e não é test run, usar Temporal
        if is_temporal_enabled() and not test_run:
            return await Engine.run_in_background(
                workflow_id=workflow_id,
                trigger_data=trigger_data,
                resume_step_id=resume_step_id,
                resume_execution_id=resume_execution_id,
            )

        # Execução síncrona (fallback ou test run)
        return await iterate_steps(
            flow_context=flow_context,
            trigger_data=trigger_data,
            test_run=test_run,
            resume_step_id=resume_step_id,
            resume_execution_id=resume_execution_id,
            until_step=until_step,
            skip_steps=skip_steps,
            mock_data=mock_data,
        )

    @staticmethod
    async def run_in_background(
        workflow_id: str,
        trigger_data: Optional[Dict[str, Any]] = None,
        resume_step_id: Optional[str] = None,
        resume_execution_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Inicia execução via Temporal (assíncrona).

        Args:
            workflow_id: ID do workflow
            trigger_data: Dados do trigger
            resume_step_id: Step a partir do qual retomar
            resume_execution_id: ID de execução a retomar

        Returns:
            Dict com execution_id e status 'running'
        """
        from app.models import WorkflowExecution
        from app.database import db
        from app.temporal.service import start_workflow_execution

        # Criar ou retomar WorkflowExecution
        if resume_execution_id:
            execution = WorkflowExecution.query.get(resume_execution_id)
            if not execution:
                raise ValueError(f"Execution {resume_execution_id} not found")
            execution.status = 'running'
        else:
            execution = WorkflowExecution(
                workflow_id=workflow_id,
                trigger_data=trigger_data or {},
                status='running',
                started_at=datetime.utcnow(),
            )
            db.session.add(execution)

        db.session.commit()

        # Iniciar via Temporal
        await start_workflow_execution(
            execution_id=str(execution.id),
            workflow_id=workflow_id,
            trigger_data=trigger_data,
            resume_step_id=resume_step_id,
        )

        return {
            'execution_id': str(execution.id),
            'status': 'running',
            'mode': 'temporal',
        }

    @staticmethod
    async def run_step(
        step_id: str,
        execution_id: str,
        parameters: Dict[str, Any] = None,
        context: Any = None,
    ) -> Dict[str, Any]:
        """
        Executa um step individual.

        Args:
            step_id: ID do WorkflowNode
            execution_id: ID da WorkflowExecution
            parameters: Parâmetros já processados (computeParameters já aplicado)
            context: GlobalVariable context

        Returns:
            Dict com resultado do step
        """
        from app.models import WorkflowNode, ExecutionStep
        from app.engine.action.process import process_action_step
        from app.engine.trigger.process import process_trigger_step
        from app.database import db
        from app.engine.compute_parameters import compute_parameters

        # Carregar node
        node = WorkflowNode.query.get(step_id)
        if not node:
            raise ValueError(f"Node {step_id} not found")

        # Criar ExecutionStep
        execution_step = ExecutionStep.create_for_node(
            execution_id=execution_id,
            node=node,
            data_in=parameters,
        )
        db.session.add(execution_step)
        execution_step.start()
        db.session.commit()

        try:
            # Determinar se é trigger ou action
            if node.is_trigger():
                result = await process_trigger_step(
                    node=node,
                    trigger_data=parameters,
                    context=context,
                )
            else:
                result = await process_action_step(
                    node=node,
                    parameters=parameters,
                    context=context,
                )

            # Marcar como sucesso
            execution_step.complete(data_out=result)
            db.session.commit()

            return result

        except Exception as e:
            # Marcar como falha
            execution_step.fail(
                error_details=str(e),
                error_code=type(e).__name__,
            )
            db.session.commit()
            raise

    @staticmethod
    def get_app_for_node(node_type: str):
        """
        Obtém o app correspondente a um tipo de node.

        Args:
            node_type: Tipo do node (ex: 'google-docs', 'hubspot')

        Returns:
            App instance ou None
        """
        from app.apps import AppRegistry
        return AppRegistry.get_by_node_type(node_type)


# Função helper para execução simples
async def run_workflow(
    workflow_id: str,
    trigger_data: Dict[str, Any] = None,
    test_run: bool = False,
) -> Dict[str, Any]:
    """
    Atalho para Engine.run().

    Args:
        workflow_id: ID do workflow
        trigger_data: Dados do trigger
        test_run: Executar em modo teste (síncrono)

    Returns:
        Resultado da execução
    """
    return await Engine.run(
        workflow_id=workflow_id,
        trigger_data=trigger_data,
        test_run=test_run,
    )
