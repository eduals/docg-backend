"""
Activities base - Operações utilitárias de execução.
"""
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from temporalio import activity

logger = logging.getLogger(__name__)


@activity.defn
async def load_execution(execution_id: str) -> Dict[str, Any]:
    """
    Carrega dados da execução e workflow do banco.
    
    Args:
        execution_id: ID da WorkflowExecution
    
    Returns:
        Dict com execution, workflow e nodes
    """
    from app.database import db
    from app.models import WorkflowExecution, Workflow, WorkflowNode
    from flask import current_app
    
    # Precisa do contexto Flask para acessar o banco
    with current_app.app_context():
        execution = WorkflowExecution.query.get(execution_id)
        if not execution:
            raise ValueError(f'Execução não encontrada: {execution_id}')
        
        workflow = Workflow.query.get(execution.workflow_id)
        if not workflow:
            raise ValueError(f'Workflow não encontrado: {execution.workflow_id}')
        
        nodes = WorkflowNode.query.filter_by(
            workflow_id=workflow.id
        ).order_by(WorkflowNode.position).all()
        
        activity.logger.info(f"Carregada execução {execution_id} com {len(nodes)} nodes")
        
        return {
            'execution': execution.to_dict(include_logs=True),
            'workflow': workflow.to_dict(),
            'nodes': [n.to_dict(include_config=True) for n in nodes],
            'organization_id': str(workflow.organization_id)
        }


@activity.defn
async def update_current_node(data: Dict[str, Any]) -> bool:
    """
    Atualiza o node atual sendo executado.
    
    Args:
        data: {execution_id, node_id}
    """
    from app.database import db
    from app.models import WorkflowExecution
    from flask import current_app
    
    with current_app.app_context():
        execution = WorkflowExecution.query.get(data['execution_id'])
        if not execution:
            raise ValueError(f'Execução não encontrada: {data["execution_id"]}')
        
        execution.current_node_id = data['node_id']
        db.session.commit()
        
        activity.logger.info(f"Node atual atualizado para {data['node_id']}")
        return True


@activity.defn
async def save_execution_context(data: Dict[str, Any]) -> bool:
    """
    Salva snapshot do ExecutionContext no banco.
    
    Args:
        data: {execution_id, context}
    """
    from app.database import db
    from app.models import WorkflowExecution
    from flask import current_app
    
    with current_app.app_context():
        execution = WorkflowExecution.query.get(data['execution_id'])
        if not execution:
            raise ValueError(f'Execução não encontrada: {data["execution_id"]}')
        
        execution.execution_context = data['context']
        db.session.commit()
        
        activity.logger.info(f"Context salvo para execução {data['execution_id']}")
        return True


@activity.defn
async def pause_execution(execution_id: str) -> bool:
    """
    Marca execução como pausada.
    
    Args:
        execution_id: ID da execução
    """
    from app.database import db
    from app.models import WorkflowExecution
    from flask import current_app
    
    with current_app.app_context():
        execution = WorkflowExecution.query.get(execution_id)
        if not execution:
            raise ValueError(f'Execução não encontrada: {execution_id}')
        
        execution.status = 'paused'
        db.session.commit()
        
        activity.logger.info(f"Execução {execution_id} pausada")
        return True


@activity.defn
async def resume_execution(execution_id: str) -> bool:
    """
    Marca execução como running (retomada).
    
    Args:
        execution_id: ID da execução
    """
    from app.database import db
    from app.models import WorkflowExecution
    from flask import current_app
    
    with current_app.app_context():
        execution = WorkflowExecution.query.get(execution_id)
        if not execution:
            raise ValueError(f'Execução não encontrada: {execution_id}')
        
        execution.status = 'running'
        db.session.commit()
        
        activity.logger.info(f"Execução {execution_id} retomada")
        return True


@activity.defn
async def complete_execution(execution_id: str) -> bool:
    """
    Marca execução como completa.
    
    Args:
        execution_id: ID da execução
    """
    from app.database import db
    from app.models import WorkflowExecution
    from flask import current_app
    
    with current_app.app_context():
        execution = WorkflowExecution.query.get(execution_id)
        if not execution:
            raise ValueError(f'Execução não encontrada: {execution_id}')
        
        execution.status = 'completed'
        execution.completed_at = datetime.utcnow()
        
        if execution.started_at:
            execution.execution_time_ms = int(
                (execution.completed_at - execution.started_at).total_seconds() * 1000
            )
        
        db.session.commit()
        
        activity.logger.info(f"Execução {execution_id} completada em {execution.execution_time_ms}ms")
        return True


@activity.defn
async def fail_execution(data: Dict[str, Any]) -> bool:
    """
    Marca execução como falha.
    
    Args:
        data: {execution_id, error_message}
    """
    from app.database import db
    from app.models import WorkflowExecution
    from flask import current_app
    
    with current_app.app_context():
        execution = WorkflowExecution.query.get(data['execution_id'])
        if not execution:
            raise ValueError(f'Execução não encontrada: {data["execution_id"]}')
        
        execution.status = 'failed'
        execution.error_message = data.get('error_message', 'Erro desconhecido')
        execution.completed_at = datetime.utcnow()
        
        if execution.started_at:
            execution.execution_time_ms = int(
                (execution.completed_at - execution.started_at).total_seconds() * 1000
            )
        
        db.session.commit()
        
        activity.logger.error(f"Execução {data['execution_id']} falhou: {execution.error_message}")
        return True


@activity.defn
async def add_execution_log(data: Dict[str, Any]) -> bool:
    """
    Adiciona log de execução de um node.
    
    Args:
        data: {
            execution_id,
            node_id,
            node_type,
            status,
            started_at,
            completed_at,
            output,
            error
        }
    """
    from app.database import db
    from app.models import WorkflowExecution
    from flask import current_app
    
    with current_app.app_context():
        execution = WorkflowExecution.query.get(data['execution_id'])
        if not execution:
            raise ValueError(f'Execução não encontrada: {data["execution_id"]}')
        
        # Parsear datas se forem strings
        started_at = data.get('started_at')
        completed_at = data.get('completed_at')
        
        if isinstance(started_at, str):
            started_at = datetime.fromisoformat(started_at)
        if isinstance(completed_at, str):
            completed_at = datetime.fromisoformat(completed_at)
        
        execution.add_log(
            node_id=data['node_id'],
            node_type=data['node_type'],
            status=data['status'],
            started_at=started_at,
            completed_at=completed_at,
            output=data.get('output'),
            error=data.get('error')
        )
        
        db.session.commit()
        
        activity.logger.info(f"Log adicionado para node {data['node_id']}: {data['status']}")
        return True

