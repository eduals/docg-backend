import uuid
from datetime import datetime
from app.database import db
from sqlalchemy.dialects.postgresql import UUID, JSONB

class DataSourceConnection(db.Model):
    __tablename__ = 'data_source_connections'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = db.Column(UUID(as_uuid=True), db.ForeignKey('organizations.id'), nullable=False)
    source_type = db.Column(db.String(50), nullable=False)  # hubspot, google_forms, etc.
    name = db.Column(db.String(255))
    credentials = db.Column(JSONB)  # Criptografado
    config = db.Column(JSONB)
    status = db.Column(db.String(50), default='active')  # active, expired, error
    last_sync_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    # workflows = db.relationship('Workflow', backref='source_connection', lazy='dynamic')  # REMOVED: workflows.source_connection_id dropado na migration JSONB
    documents = db.relationship('GeneratedDocument', backref='source_connection', lazy='dynamic')
    
    # Para HubSpot - campos de conveniência
    @property
    def portal_id(self):
        return self.config.get('portal_id') if self.config else None
    
    @property
    def access_token(self):
        return self.credentials.get('access_token') if self.credentials else None
    
    def get_decrypted_credentials(self):
        """Retorna credenciais descriptografadas"""
        if not self.credentials or not self.credentials.get('encrypted'):
            return {}
        from app.utils.encryption import decrypt_credentials
        return decrypt_credentials(self.credentials['encrypted'])
    
    def to_dict(self, include_credentials=False):
        result = {
            'id': str(self.id),
            'organization_id': str(self.organization_id),
            'source_type': self.source_type,
            'name': self.name,
            'config': self.config,
            'status': self.status,
            'last_sync_at': self.last_sync_at.isoformat() if self.last_sync_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        if include_credentials:
            result['credentials'] = self.credentials
        
        return result

