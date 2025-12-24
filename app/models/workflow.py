import uuid
from datetime import datetime
from app.database import db
from sqlalchemy.dialects.postgresql import UUID, JSONB

# Node type constants (mantido para compatibilidade)
TRIGGER_NODE_TYPES = ['hubspot', 'webhook', 'google-forms', 'trigger']


class Workflow(db.Model):
    __tablename__ = 'workflows'

    # IDs
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = db.Column(UUID(as_uuid=True), db.ForeignKey('organizations.id'), nullable=False)

    # Metadata
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(50), default='draft')  # draft, active, paused, archived
    visibility = db.Column(db.String(20), default='private')  # private, public

    # ⭐ Workflow Structure (React Flow format)
    nodes = db.Column(JSONB, nullable=False, default=list)  # Array of workflow nodes
    edges = db.Column(JSONB, nullable=False, default=list)  # Array of node connections

    # Timestamps
    created_by = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    creator = db.relationship('User', foreign_keys=[created_by])
    documents = db.relationship('GeneratedDocument', backref='workflow', lazy='dynamic')
    executions = db.relationship('WorkflowExecution', backref='workflow', lazy='dynamic')

    def to_dict(self):
        """Convert workflow to dictionary."""
        return {
            'id': str(self.id),
            'organization_id': str(self.organization_id),
            'name': self.name,
            'description': self.description,
            'status': self.status,
            'visibility': self.visibility,
            'nodes': self.nodes or [],
            'edges': self.edges or [],
            'created_by': str(self.created_by) if self.created_by else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
