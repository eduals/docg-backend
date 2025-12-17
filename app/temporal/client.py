"""
Cliente Temporal para conectar ao servidor e enviar signals.
"""
import asyncio
import logging
from typing import Optional, Any, Dict
from temporalio.client import Client, WorkflowHandle

from .config import get_config, SignalNames

logger = logging.getLogger(__name__)

# Cliente singleton
_client: Optional[Client] = None


async def get_temporal_client() -> Client:
    """
    Retorna cliente Temporal (singleton).
    Cria conexão se ainda não existir.
    """
    global _client
    
    if _client is None:
        config = get_config()
        logger.info(f"Conectando ao Temporal Server: {config.address}")
        
        _client = await Client.connect(
            config.address,
            namespace=config.namespace
        )
        
        logger.info(f"Conectado ao Temporal Server no namespace: {config.namespace}")
    
    return _client


async def get_workflow_handle(workflow_id: str) -> WorkflowHandle:
    """
    Obtém handle de um workflow existente.
    
    Args:
        workflow_id: ID do workflow (temporal_workflow_id)
    
    Returns:
        Handle para interagir com o workflow
    """
    client = await get_temporal_client()
    return client.get_workflow_handle(workflow_id)


async def send_signal(workflow_id: str, signal_name: str, payload: Dict[str, Any]) -> bool:
    """
    Envia signal para um workflow.
    
    Args:
        workflow_id: ID do workflow no Temporal
        signal_name: Nome do signal (ver SignalNames)
        payload: Dados do signal
    
    Returns:
        True se enviou com sucesso
    """
    try:
        handle = await get_workflow_handle(workflow_id)
        await handle.signal(signal_name, payload)
        logger.info(f"Signal '{signal_name}' enviado para workflow {workflow_id}")
        return True
    except Exception as e:
        logger.error(f"Erro ao enviar signal '{signal_name}' para {workflow_id}: {e}")
        raise


async def send_approval_signal(workflow_id: str, approval_id: str, decision: str) -> bool:
    """
    Envia signal de decisão de aprovação.
    
    Args:
        workflow_id: ID do workflow no Temporal
        approval_id: ID da aprovação
        decision: 'approved' ou 'rejected'
    """
    return await send_signal(
        workflow_id=workflow_id,
        signal_name=SignalNames.APPROVAL_DECISION,
        payload={
            'approval_id': approval_id,
            'decision': decision
        }
    )


async def send_signature_signal(workflow_id: str, signature_request_id: str, status: str) -> bool:
    """
    Envia signal de atualização de assinatura.
    
    Args:
        workflow_id: ID do workflow no Temporal
        signature_request_id: ID da SignatureRequest
        status: Status da assinatura ('signed', 'declined', etc.)
    """
    return await send_signal(
        workflow_id=workflow_id,
        signal_name=SignalNames.SIGNATURE_UPDATE,
        payload={
            'signature_request_id': signature_request_id,
            'status': status
        }
    )


def send_signal_sync(workflow_id: str, signal_name: str, payload: Dict[str, Any]) -> bool:
    """
    Versão síncrona de send_signal para uso em contextos não-async (Flask).
    
    Cria um novo event loop se necessário.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Se já tem loop rodando, criar task
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(
                    asyncio.run,
                    send_signal(workflow_id, signal_name, payload)
                )
                return future.result(timeout=30)
        else:
            return loop.run_until_complete(
                send_signal(workflow_id, signal_name, payload)
            )
    except RuntimeError:
        # Não tem event loop, criar um novo
        return asyncio.run(send_signal(workflow_id, signal_name, payload))


def send_approval_signal_sync(workflow_id: str, approval_id: str, decision: str) -> bool:
    """Versão síncrona de send_approval_signal"""
    return send_signal_sync(
        workflow_id=workflow_id,
        signal_name=SignalNames.APPROVAL_DECISION,
        payload={
            'approval_id': approval_id,
            'decision': decision
        }
    )


def send_signature_signal_sync(workflow_id: str, signature_request_id: str, status: str) -> bool:
    """Versão síncrona de send_signature_signal"""
    return send_signal_sync(
        workflow_id=workflow_id,
        signal_name=SignalNames.SIGNATURE_UPDATE,
        payload={
            'signature_request_id': signature_request_id,
            'status': status
        }
    )

