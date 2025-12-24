import uuid
from datetime import datetime
from app.database import db
from sqlalchemy.dialects.postgresql import UUID, JSONB

class SignatureRequest(db.Model):
    __tablename__ = 'signature_requests'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = db.Column(UUID(as_uuid=True), db.ForeignKey('organizations.id'), nullable=False)
    generated_document_id = db.Column(UUID(as_uuid=True), db.ForeignKey('generated_documents.id'), nullable=False)
    
    # === Temporal Workflow Tracking ===
    # Qual node criou esta request (ID do node no workflow.nodes JSONB)
    node_id = db.Column(db.String(255), nullable=True)
    # Qual execução criou esta request
    workflow_execution_id = db.Column(UUID(as_uuid=True), db.ForeignKey('workflow_executions.id', ondelete='SET NULL'), nullable=True)
    
    # Provider
    provider = db.Column(db.String(50), nullable=False)
    external_id = db.Column(db.String(255))
    external_url = db.Column(db.String(500))
    
    # Status
    status = db.Column(db.String(50), default='pending')
    # pending, sent, viewed, signed, declined, expired, error
    
    # Signers
    signers = db.Column(JSONB)
    # Status por signatário: {"email@ex.com": "signed", "email2@ex.com": "pending"}
    signers_status = db.Column(JSONB, default=dict)
    
    # Timestamps
    sent_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    expires_at = db.Column(db.DateTime)
    webhook_data = db.Column(JSONB)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    workflow_execution = db.relationship('WorkflowExecution', foreign_keys=[workflow_execution_id], backref='signature_requests')
    
    def all_signed(self) -> bool:
        """
        Verifica se todos os signatários assinaram.
        Usado para determinar quando retomar o workflow.
        """
        if not self.signers_status:
            # Se não tem status por signatário, verificar status geral
            return self.status == 'signed'
        
        # Verificar se todos estão como 'signed'
        return all(status == 'signed' for status in self.signers_status.values())
    
    def update_signer_status(self, email: str, status: str):
        """Atualiza status de um signatário específico"""
        if self.signers_status is None:
            self.signers_status = {}
        
        signers_status = dict(self.signers_status)
        signers_status[email.lower()] = status
        self.signers_status = signers_status
        
        # Se todos assinaram, atualizar status geral
        if self.all_signed():
            self.status = 'signed'
            self.completed_at = datetime.utcnow()
    
    def to_dict(self):
        return {
            'id': str(self.id),
            'organization_id': str(self.organization_id),
            'generated_document_id': str(self.generated_document_id),
            'node_id': str(self.node_id) if self.node_id else None,
            'workflow_execution_id': str(self.workflow_execution_id) if self.workflow_execution_id else None,
            'provider': self.provider,
            'external_id': self.external_id,
            'external_url': self.external_url,
            'status': self.status,
            'signers': self.signers,
            'signers_status': self.signers_status,
            'all_signed': self.all_signed(),
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

