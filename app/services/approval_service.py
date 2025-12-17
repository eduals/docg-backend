"""
Serviço para gerenciar retomada de execuções de workflow após aprovação.
"""
import logging
from datetime import datetime
from app.database import db
from app.models import WorkflowApproval, WorkflowExecution, WorkflowNode
from app.services.workflow_executor import WorkflowExecutor, ExecutionContext

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
    
    # Buscar node atual (o node de human-in-loop)
    current_node = WorkflowNode.query.get(approval.node_id)
    if not current_node:
        raise ValueError(f'Node não encontrado: {approval.node_id}')
    
    # Buscar próximo node
    next_node = WorkflowNode.query.filter_by(
        workflow_id=workflow.id,
        position=current_node.position + 1
    ).first()
    
    if not next_node:
        # Não há próximo node, marcar execução como concluída
        execution.status = 'completed'
        db.session.commit()
        logger.info(f'Execução {execution.id} concluída após aprovação')
        return
    
    # Continuar execução a partir do próximo node
    executor = WorkflowExecutor()
    
    try:
        # Executar nodes restantes
        nodes_to_execute = WorkflowNode.query.filter(
            WorkflowNode.workflow_id == workflow.id,
            WorkflowNode.position > current_node.position
        ).order_by(WorkflowNode.position).all()
        
        for node in nodes_to_execute:
            if not node.is_configured():
                logger.warning(f'Node {node.id} não configurado, pulando')
                continue
            
            node_executor = executor.executors.get(node.node_type)
            if not node_executor:
                logger.warning(f'Executor não encontrado para node_type: {node.node_type}')
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

