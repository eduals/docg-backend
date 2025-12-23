import uuid
from datetime import datetime
from enum import Enum
from app.database import db
from sqlalchemy.dialects.postgresql import UUID, JSONB


class ExecutionStatus(str, Enum):
    """
    Estados possíveis de uma execução de workflow.

    Fluxo típico:
    queued → running → (needs_review)? → ready → sending → sent → signing → signed → completed

    Ou em caso de erro:
    running → failed

    Ou cancelamento:
    running → canceled
    """
    QUEUED = 'queued'           # Na fila, aguardando início
    RUNNING = 'running'         # Executando
    NEEDS_REVIEW = 'needs_review'  # Bloqueado por preflight/erro recuperável
    READY = 'ready'             # Preflight ok, pronto para continuar
    SENDING = 'sending'         # Enviando documento
    SENT = 'sent'               # Documento enviado
    SIGNING = 'signing'         # Aguardando assinaturas
    SIGNED = 'signed'           # Todas assinaturas coletadas
    COMPLETED = 'completed'     # Finalizado com sucesso (alias para sent/signed)
    FAILED = 'failed'           # Erro irrecuperável
    CANCELED = 'canceled'       # Cancelado pelo usuário
    PAUSED = 'paused'           # Pausado manualmente


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
    
    status = db.Column(db.String(50), default=ExecutionStatus.RUNNING.value)

    # === Progresso e estado atual ===
    # Progresso de 0-100
    progress = db.Column(db.Integer, default=0)

    # Step atual sendo executado
    # Estrutura: {index: 2, label: "Gerando documento", node_id: "uuid", node_type: "google-docs"}
    current_step = db.Column(JSONB, nullable=True)

    # === Erros separados (humano/técnico) ===
    error_message = db.Column(db.Text)  # DEPRECATED: usar last_error_human
    last_error_human = db.Column(db.Text, nullable=True)  # "Não foi possível acessar o arquivo"
    last_error_tech = db.Column(db.Text, nullable=True)   # "google.api.PermissionDenied: 403"

    # === Preflight ===
    # Sumário do preflight check
    # Estrutura: {blocking_count: 2, warning_count: 1, completed_at: "ISO", groups: {...}}
    preflight_summary = db.Column(JSONB, nullable=True)

    # === Estados de delivery e signature (agregados) ===
    delivery_state = db.Column(db.String(20), nullable=True)   # pending, sending, sent, failed
    signature_state = db.Column(db.String(20), nullable=True)  # pending, signing, signed, declined, expired

    # === Ações recomendadas ===
    # Lista de ações que o usuário pode tomar para resolver issues
    # Estrutura: [{action: "fix_permissions", target: "drive_folder", params: {...}}]
    recommended_actions = db.Column(JSONB, nullable=True)

    # === Phase Metrics (Feature 14) ===
    # Métricas por fase da execução
    # Estrutura: {
    #     "preflight": {"started_at": "ISO", "completed_at": "ISO", "duration_ms": 234},
    #     "trigger": {"started_at": "ISO", "completed_at": "ISO", "duration_ms": 567},
    #     "render": {"started_at": "ISO", "completed_at": "ISO", "duration_ms": 3456},
    #     "delivery": {"started_at": "ISO", "completed_at": "ISO", "duration_ms": 890},
    #     "signature": {"started_at": "ISO", "completed_at": "ISO", "duration_ms": null}
    # }
    phase_metrics = db.Column(JSONB, nullable=True)

    # === Correlation ID (Feature 14) ===
    # ID único para rastreamento em logs/eventos
    correlation_id = db.Column(UUID(as_uuid=True), default=uuid.uuid4)

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
            'progress': self.progress,
            'current_step': self.current_step,
            'error_message': self.error_message,  # DEPRECATED
            'last_error_human': self.last_error_human,
            'last_error_tech': self.last_error_tech,
            'preflight_summary': self.preflight_summary,
            'delivery_state': self.delivery_state,
            'signature_state': self.signature_state,
            'recommended_actions': self.recommended_actions,
            'phase_metrics': self.phase_metrics,
            'correlation_id': str(self.correlation_id) if self.correlation_id else None,
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

    # === Métodos Helper para Run State ===

    def update_progress(self, progress: int):
        """Atualiza o progresso (0-100)"""
        self.progress = max(0, min(100, progress))

    def update_current_step(self, index: int, label: str, node_id: str, node_type: str):
        """Atualiza o step atual"""
        self.current_step = {
            'index': index,
            'label': label,
            'node_id': str(node_id),
            'node_type': node_type
        }

    def set_error(self, error_human: str, error_tech: str = None):
        """Define os erros (humano e técnico)"""
        self.last_error_human = error_human
        self.last_error_tech = error_tech
        self.error_message = error_human  # Backward compatibility

    def update_preflight_summary(self, blocking_count: int, warning_count: int, groups: dict = None):
        """Atualiza o sumário do preflight"""
        self.preflight_summary = {
            'blocking_count': blocking_count,
            'warning_count': warning_count,
            'completed_at': datetime.utcnow().isoformat(),
            'groups': groups or {}
        }

    def update_delivery_state(self, state: str):
        """Atualiza o estado de delivery: pending, sending, sent, failed"""
        self.delivery_state = state

    def update_signature_state(self, state: str):
        """Atualiza o estado de assinatura: pending, signing, signed, declined, expired"""
        self.signature_state = state

    def set_recommended_actions(self, actions: list):
        """Define as ações recomendadas"""
        self.recommended_actions = actions

    def start_phase(self, phase: str):
        """Marca início de uma fase"""
        if self.phase_metrics is None:
            self.phase_metrics = {}

        self.phase_metrics[phase] = {
            'started_at': datetime.utcnow().isoformat(),
            'completed_at': None,
            'duration_ms': None
        }

    def complete_phase(self, phase: str):
        """Marca conclusão de uma fase"""
        if self.phase_metrics and phase in self.phase_metrics:
            started = datetime.fromisoformat(self.phase_metrics[phase]['started_at'])
            completed = datetime.utcnow()
            duration_ms = int((completed - started).total_seconds() * 1000)

            self.phase_metrics[phase]['completed_at'] = completed.isoformat()
            self.phase_metrics[phase]['duration_ms'] = duration_ms

