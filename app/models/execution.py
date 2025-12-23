import uuid
from datetime import datetime
from app.database import db
from sqlalchemy.dialects.postgresql import UUID, JSONB


class ConcurrentExecutionError(Exception):
    """Raised when trying to start a workflow that is already running"""
    def __init__(self, workflow_id: str, execution_id: str = None):
        self.workflow_id = workflow_id
        self.execution_id = execution_id
        message = f"Workflow {workflow_id} is already running"
        if execution_id:
            message += f" (execution: {execution_id})"
        super().__init__(message)


class WorkflowExecution(db.Model):
    __tablename__ = 'workflow_executions'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id = db.Column(UUID(as_uuid=True), db.ForeignKey('workflows.id', ondelete='CASCADE'), nullable=False)
    generated_document_id = db.Column(UUID(as_uuid=True), db.ForeignKey('generated_documents.id'))
    
    trigger_type = db.Column(db.String(50))
    trigger_data = db.Column(JSONB)
    
    status = db.Column(db.String(50), default='running')
    # running, paused, completed, failed
    error_message = db.Column(db.Text)
    
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    execution_time_ms = db.Column(db.Integer)
    
    # === Temporal Workflow Tracking ===
    # ID do workflow no Temporal Server
    temporal_workflow_id = db.Column(db.String(255), unique=True, nullable=True)
    # Run ID do Temporal (para debug/histórico)
    temporal_run_id = db.Column(db.String(255), nullable=True)
    # Node atual sendo executado
    current_node_id = db.Column(UUID(as_uuid=True), db.ForeignKey('workflow_nodes.id', ondelete='SET NULL'), nullable=True)
    # Snapshot do ExecutionContext para retomada
    execution_context = db.Column(JSONB, nullable=True)
    # Logs por node: [{node_id, node_type, started_at, completed_at, duration_ms, status, output, error}]
    execution_logs = db.Column(JSONB, default=list)
    
    # Métricas de geração de IA
    # Estrutura:
    # {
    #     "total_tags": 3,
    #     "successful": 2,
    #     "failed": 1,
    #     "total_time_ms": 4500,
    #     "total_tokens": 1200,
    #     "estimated_cost_usd": 0.024,
    #     "details": [
    #         {
    #             "tag": "paragrapho1",
    #             "provider": "openai",
    #             "model": "gpt-4",
    #             "time_ms": 2100,
    #             "tokens": 800,
    #             "status": "success"
    #         }
    #     ]
    # }
    ai_metrics = db.Column(JSONB)

    # Optimistic locking version
    version = db.Column(db.Integer, default=1, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    generated_document = db.relationship('GeneratedDocument', foreign_keys=[generated_document_id])
    current_node = db.relationship('WorkflowNode', foreign_keys=[current_node_id])

    @classmethod
    def check_concurrent_execution(cls, workflow_id: str) -> None:
        """
        Verifica se há uma execução em andamento para o workflow.

        Args:
            workflow_id: ID do workflow

        Raises:
            ConcurrentExecutionError: Se já existe uma execução running
        """
        running = cls.query.filter_by(
            workflow_id=workflow_id,
            status='running'
        ).first()

        if running:
            raise ConcurrentExecutionError(
                workflow_id=str(workflow_id),
                execution_id=str(running.id)
            )

    @classmethod
    def get_running_execution(cls, workflow_id: str):
        """
        Retorna a execução em andamento para o workflow, se existir.

        Args:
            workflow_id: ID do workflow

        Returns:
            WorkflowExecution ou None
        """
        return cls.query.filter_by(
            workflow_id=workflow_id,
            status='running'
        ).first()
    
    def to_dict(self, include_logs=False):
        result = {
            'id': str(self.id),
            'workflow_id': str(self.workflow_id),
            'generated_document_id': str(self.generated_document_id) if self.generated_document_id else None,
            'trigger_type': self.trigger_type,
            'trigger_data': self.trigger_data,
            'status': self.status,
            'error_message': self.error_message,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'execution_time_ms': self.execution_time_ms,
            'temporal_workflow_id': self.temporal_workflow_id,
            'temporal_run_id': self.temporal_run_id,
            'current_node_id': str(self.current_node_id) if self.current_node_id else None,
            'ai_metrics': self.ai_metrics,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        
        if include_logs:
            result['execution_logs'] = self.execution_logs or []
        
        return result
    
    def add_log(self, node_id: str, node_type: str, status: str, 
                started_at: datetime = None, completed_at: datetime = None,
                output: dict = None, error: str = None):
        """Adiciona log de execução de um node"""
        if self.execution_logs is None:
            self.execution_logs = []
        
        duration_ms = None
        if started_at and completed_at:
            duration_ms = int((completed_at - started_at).total_seconds() * 1000)
        
        log_entry = {
            'node_id': node_id,
            'node_type': node_type,
            'status': status,
            'started_at': started_at.isoformat() if started_at else None,
            'completed_at': completed_at.isoformat() if completed_at else None,
            'duration_ms': duration_ms,
            'output': output,
            'error': error
        }
        
        self.execution_logs = self.execution_logs + [log_entry]

