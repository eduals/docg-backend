"""
Serviço para gerenciar retomada de execuções de workflow após aprovação.
"""
import logging
from datetime import datetime
from app.database import db
from app.models import WorkflowApproval, WorkflowExecution
from app.services.workflow_executor import WorkflowExecutor, ExecutionContext
from app.engine.flow.normalization import normalize_nodes_from_jsonb

logger = logging.getLogger(__name__)


def resume_workflow_execution(approval: WorkflowApproval):
    """
    Retoma execução de workflow após aprovação.
    
    Args:
        approval: WorkflowApproval aprovado
    """
    execution = WorkflowExecution.query.get(approval.workflow_execution_id)
    if not execution:
        raise ValueError(f'Execução não encontrada: {approval.workflow_execution_id}')
    
    workflow = execution.workflow
    if not workflow:
        raise ValueError(f'Workflow não encontrado: {execution.workflow_id}')
    
    # Recriar ExecutionContext a partir do snapshot
    execution_context_data = approval.execution_context or {}
    
    context = ExecutionContext(
        workflow_id=str(workflow.id),
        execution_id=str(execution.id),
        source_object_id=execution_context_data.get('source_object_id'),
        source_object_type=execution_context_data.get('source_object_type')
    )
    context.source_data = execution_context_data.get('source_data', {})
    context.metadata = execution_context_data.get('metadata', {})
    
    # Restaurar documentos gerados
    context.generated_documents = execution_context_data.get('generated_documents', [])

    # Buscar nodes do JSONB
    nodes = normalize_nodes_from_jsonb(workflow.nodes or [], workflow.edges or [])

    # Buscar node atual (o node de human-in-loop)
    current_node = None
    current_position = 0
    for node in nodes:
        if node.get('id') == approval.node_id:
            current_node = node
            current_position = node.get('position', 0)
            break

    if not current_node:
        raise ValueError(f'Node não encontrado: {approval.node_id}')

    # Buscar próximo node
    next_node = None
    for node in nodes:
        if node.get('position', 0) == current_position + 1:
            next_node = node
            break

    if not next_node:
        # Não há próximo node, marcar execução como concluída
        execution.status = 'completed'
        db.session.commit()
        logger.info(f'Execução {execution.id} concluída após aprovação')
        return

    # Continuar execução a partir do próximo node
    executor = WorkflowExecutor()

    try:
        # Executar nodes restantes (nodes com position > current_position)
        nodes_to_execute = [
            n for n in nodes
            if n.get('position', 0) > current_position
        ]

        for node in nodes_to_execute:
            # Verificar se node está configurado (tem config não vazio)
            config = node.get('config', {})
            if not config:
                logger.warning(f'Node {node.get("id")} não configurado, pulando')
                continue

            node_type = node.get('node_type')
            node_executor = executor.executors.get(node_type)
            if not node_executor:
                logger.warning(f'Executor não encontrado para node_type: {node_type}')
                continue

            context = node_executor.execute(node, context)
        
        # Marcar execução como concluída
        execution.status = 'completed'
        db.session.commit()
        
        logger.info(f'Execução {execution.id} retomada e concluída após aprovação')
        
    except Exception as e:
        logger.exception(f'Erro ao retomar execução: {str(e)}')
        execution.status = 'failed'
        execution.error_message = str(e)
        db.session.commit()
        raise

