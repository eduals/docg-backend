import uuid
from datetime import datetime
from app.database import db
from sqlalchemy.dialects.postgresql import UUID, JSONB

class WorkflowExecution(db.Model):
    __tablename__ = 'workflow_executions'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id = db.Column(UUID(as_uuid=True), db.ForeignKey('workflows.id'), nullable=False)
    generated_document_id = db.Column(UUID(as_uuid=True), db.ForeignKey('generated_documents.id'))
    
    trigger_type = db.Column(db.String(50))
    trigger_data = db.Column(JSONB)
    
    status = db.Column(db.String(50), default='running')
    # running, completed, failed
    error_message = db.Column(db.Text)
    
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    execution_time_ms = db.Column(db.Integer)
    
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
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    generated_document = db.relationship('GeneratedDocument', foreign_keys=[generated_document_id])
    
    def to_dict(self):
        return {
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
            'ai_metrics': self.ai_metrics,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

