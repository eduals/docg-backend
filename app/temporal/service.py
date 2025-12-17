"""
Serviço de integração Temporal - Funções para uso na API Flask.

Este módulo fornece funções síncronas para:
- Iniciar execuções de workflow via Temporal
- Enviar signals (aprovação, assinatura)
"""
import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


def start_workflow_execution(
    execution_id: str,
    workflow_id: str = None
) -> Dict[str, Any]:
    """
    Inicia execução de workflow via Temporal.
    
    Deve ser chamado após criar o WorkflowExecution no banco.
    
    Args:
        execution_id: ID da WorkflowExecution criada
        workflow_id: ID do Workflow (opcional, para logging)
    
    Returns:
        {temporal_workflow_id, temporal_run_id}
    """
    from app.database import db
    from app.models import WorkflowExecution
    from .config import get_config
    
    execution = WorkflowExecution.query.get(execution_id)
    if not execution:
        raise ValueError(f'Execução não encontrada: {execution_id}')
    
    config = get_config()
    
    # Gerar ID do Temporal workflow
    temporal_workflow_id = f"exec_{execution_id}"
    
    async def _start():
        from temporalio.client import Client
        
        client = await Client.connect(
            config.address,
            namespace=config.namespace
        )
        
        # Iniciar workflow
        handle = await client.start_workflow(
            "DocGWorkflow",
            execution_id,
            id=temporal_workflow_id,
            task_queue=config.task_queue
        )
        
        return {
            'temporal_workflow_id': temporal_workflow_id,
            'temporal_run_id': handle.result_run_id
        }
    
    # Executar async
    result = _run_async(_start())
    
    # Atualizar execution com IDs do Temporal
    execution.temporal_workflow_id = result['temporal_workflow_id']
    execution.temporal_run_id = result.get('temporal_run_id')
    db.session.commit()
    
    logger.info(f"Workflow iniciado no Temporal: {temporal_workflow_id}")
    
    return result


def send_approval_decision(
    workflow_execution_id: str,
    approval_id: str,
    decision: str
) -> bool:
    """
    Envia decisão de aprovação para o workflow.
    
    Args:
        workflow_execution_id: ID da WorkflowExecution
        approval_id: ID da WorkflowApproval
        decision: 'approved' ou 'rejected'
    
    Returns:
        True se enviou com sucesso
    """
    from app.models import WorkflowExecution
    from .config import SignalNames
    
    execution = WorkflowExecution.query.get(workflow_execution_id)
    if not execution:
        raise ValueError(f'Execução não encontrada: {workflow_execution_id}')
    
    if not execution.temporal_workflow_id:
        raise ValueError(f'Execução {workflow_execution_id} não tem temporal_workflow_id')
    
    async def _send():
        from .client import send_approval_signal
        return await send_approval_signal(
            execution.temporal_workflow_id,
            approval_id,
            decision
        )
    
    result = _run_async(_send())
    logger.info(f"Signal de aprovação enviado: {decision} para {execution.temporal_workflow_id}")
    
    return result


def send_signature_update(
    workflow_execution_id: str,
    signature_request_id: str,
    status: str
) -> bool:
    """
    Envia update de assinatura para o workflow.
    
    Args:
        workflow_execution_id: ID da WorkflowExecution
        signature_request_id: ID da SignatureRequest
        status: 'signed', 'declined', etc.
    
    Returns:
        True se enviou com sucesso
    """
    from app.models import WorkflowExecution
    
    execution = WorkflowExecution.query.get(workflow_execution_id)
    if not execution:
        raise ValueError(f'Execução não encontrada: {workflow_execution_id}')
    
    if not execution.temporal_workflow_id:
        raise ValueError(f'Execução {workflow_execution_id} não tem temporal_workflow_id')
    
    async def _send():
        from .client import send_signature_signal
        return await send_signature_signal(
            execution.temporal_workflow_id,
            signature_request_id,
            status
        )
    
    result = _run_async(_send())
    logger.info(f"Signal de assinatura enviado: {status} para {execution.temporal_workflow_id}")
    
    return result


def _run_async(coro):
    """
    Executa coroutine em contexto síncrono.
    
    Tenta usar o event loop existente ou cria um novo.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Estamos dentro de um loop (ex: pytest-asyncio)
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, coro)
                return future.result(timeout=60)
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        # Não tem event loop
        return asyncio.run(coro)


def is_temporal_enabled() -> bool:
    """
    Verifica se Temporal está habilitado (variáveis de ambiente configuradas).
    """
    import os
    return bool(os.getenv('TEMPORAL_ADDRESS'))


def execute_workflow_sync_fallback(
    workflow_id: str,
    source_object_id: str,
    source_object_type: str,
    user_id: str = None
) -> 'WorkflowExecution':
    """
    Fallback: Executa workflow sincronamente (sem Temporal).
    
    Usado quando Temporal não está configurado.
    """
    from app.models import Workflow
    from app.services.workflow_executor import WorkflowExecutor
    
    workflow = Workflow.query.get(workflow_id)
    if not workflow:
        raise ValueError(f'Workflow não encontrado: {workflow_id}')
    
    executor = WorkflowExecutor()
    return executor.execute_workflow(
        workflow,
        source_object_id,
        source_object_type,
        user_id
    )

