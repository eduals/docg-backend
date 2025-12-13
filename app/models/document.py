import uuid
from datetime import datetime
from app.database import db
from sqlalchemy.dialects.postgresql import UUID, JSONB

class GeneratedDocument(db.Model):
    __tablename__ = 'generated_documents'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = db.Column(UUID(as_uuid=True), db.ForeignKey('organizations.id'), nullable=False)
    workflow_id = db.Column(UUID(as_uuid=True), db.ForeignKey('workflows.id', ondelete='SET NULL'))
    
    # Source reference
    source_connection_id = db.Column(UUID(as_uuid=True), db.ForeignKey('data_source_connections.id'))
    source_object_type = db.Column(db.String(100))
    source_object_id = db.Column(db.String(255))
    
    # Template used
    template_id = db.Column(UUID(as_uuid=True), db.ForeignKey('templates.id'))
    template_version = db.Column(db.Integer)
    
    # Generated document
    name = db.Column(db.String(500))
    google_doc_id = db.Column(db.String(255))
    google_doc_url = db.Column(db.String(500))
    pdf_file_id = db.Column(db.String(255))
    pdf_url = db.Column(db.String(500))
    
    # HubSpot attachment (if attached)
    hubspot_file_id = db.Column(db.String(255))
    hubspot_file_url = db.Column(db.String(500))
    hubspot_attachment_id = db.Column(db.String(255))  # ID do engagement criado
    
    # Status
    status = db.Column(db.String(50), default='generating')
    # generating, generated, error, sent_for_signature, signed, expired
    error_message = db.Column(db.Text)
    
    # Metadata
    generated_data = db.Column(JSONB)
    generated_by = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'))
    generated_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    generator = db.relationship('User', foreign_keys=[generated_by])
    signature_requests = db.relationship('SignatureRequest', backref='document', lazy='dynamic')
    
    def to_dict(self, include_details=False):
        result = {
            'id': str(self.id),
            'name': self.name,
            'status': self.status,
            'google_doc_url': self.google_doc_url,
            'pdf_url': self.pdf_url,
            'source_object_type': self.source_object_type,
            'source_object_id': self.source_object_id,
            'generated_at': self.generated_at.isoformat() if self.generated_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        
        # Incluir informações do HubSpot se disponíveis
        if self.hubspot_file_id:
            result['hubspot_file_id'] = self.hubspot_file_id
            result['hubspot_file_url'] = self.hubspot_file_url
            if self.hubspot_attachment_id:
                result['hubspot_attachment_id'] = self.hubspot_attachment_id
        
        if include_details:
            result.update({
                'workflow_id': str(self.workflow_id) if self.workflow_id else None,
                'template_id': str(self.template_id) if self.template_id else None,
                'generated_data': self.generated_data,
                'error_message': self.error_message
            })
        
        return result

