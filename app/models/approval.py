"""
Modelo para aprovações de workflow (Human-in-the-Loop).
"""
import uuid
from datetime import datetime, timedelta
from app.database import db
from sqlalchemy.dialects.postgresql import UUID, JSONB

class WorkflowApproval(db.Model):
    """
    Representa uma aprovação pendente em um workflow.
    Usado para pausar execução e aguardar aprovação humana.
    """
    __tablename__ = 'workflow_approvals'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_execution_id = db.Column(UUID(as_uuid=True), db.ForeignKey('workflow_executions.id', ondelete='CASCADE'), nullable=False)
    workflow_id = db.Column(UUID(as_uuid=True), db.ForeignKey('workflows.id', ondelete='CASCADE'), nullable=False)
    node_id = db.Column(db.String(255), nullable=False)  # ID do node no workflow.nodes JSONB
    
    # Snapshot do ExecutionContext no momento da pausa
    execution_context = db.Column(JSONB)
    
    # Aprovação
    approver_email = db.Column(db.String(255), nullable=False)
    approval_token = db.Column(db.String(255), unique=True, nullable=False)
    status = db.Column(db.String(50), default='pending')  # pending, approved, rejected, expired
    
    # Configuração
    message_template = db.Column(db.Text)
    timeout_hours = db.Column(db.Integer, default=48)
    auto_approve_on_timeout = db.Column(db.Boolean, default=False)
    
    # Documentos para revisão
    document_urls = db.Column(JSONB)  # Array de URLs dos documentos gerados
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    approved_at = db.Column(db.DateTime)
    rejected_at = db.Column(db.DateTime)
    expires_at = db.Column(db.DateTime)
    
    # Comentário de rejeição (opcional)
    rejection_comment = db.Column(db.Text)
    
    # Relationships
    workflow_execution = db.relationship('WorkflowExecution', backref='approvals', foreign_keys=[workflow_execution_id])
    workflow = db.relationship('Workflow', backref='approvals', foreign_keys=[workflow_id])
    
    # Índices
    __table_args__ = (
        db.Index('idx_approval_token', 'approval_token', unique=True),
        db.Index('idx_approval_execution', 'workflow_execution_id'),
        db.Index('idx_approval_status', 'status'),
        db.Index('idx_approval_expires', 'expires_at'),
    )
    
    def to_dict(self):
        """Converte aprovação para dicionário"""
        return {
            'id': str(self.id),
            'workflow_execution_id': str(self.workflow_execution_id),
            'workflow_id': str(self.workflow_id),
            'node_id': str(self.node_id),
            'approver_email': self.approver_email,
            'approval_token': self.approval_token,
            'status': self.status,
            'message_template': self.message_template,
            'timeout_hours': self.timeout_hours,
            'auto_approve_on_timeout': self.auto_approve_on_timeout,
            'document_urls': self.document_urls or [],
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'approved_at': self.approved_at.isoformat() if self.approved_at else None,
            'rejected_at': self.rejected_at.isoformat() if self.rejected_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'rejection_comment': self.rejection_comment
        }
    
    def is_expired(self):
        """Verifica se a aprovação expirou"""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at
    
    def generate_approval_token(self):
        """Gera token único para aprovação"""
        import secrets
        self.approval_token = secrets.token_urlsafe(32)
        return self.approval_token

