import uuid
from datetime import datetime
from app.database import db
from sqlalchemy.dialects.postgresql import UUID, JSONB

class Template(db.Model):
    __tablename__ = 'templates'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = db.Column(UUID(as_uuid=True), db.ForeignKey('organizations.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    google_file_id = db.Column(db.String(255), nullable=True)  # Pode ser None se for Microsoft
    google_file_type = db.Column(db.String(50), nullable=True)  # document, presentation - Pode ser None se for Microsoft
    google_file_url = db.Column(db.String(500))
    thumbnail_url = db.Column(db.String(500))
    # Microsoft fields
    microsoft_file_id = db.Column(db.String(255))  # ID do arquivo no OneDrive/SharePoint
    microsoft_file_type = db.Column(db.String(50))  # 'word', 'powerpoint'
    detected_tags = db.Column(JSONB)  # ["contact.firstname", "deal.amount", ...]
    version = db.Column(db.Integer, default=1)
    last_synced_at = db.Column(db.DateTime)
    created_by = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Storage fields (para templates enviados)
    storage_type = db.Column(db.String(50))  # 'google', 'microsoft', 'uploaded'
    storage_file_url = db.Column(db.String(500))  # URL no DigitalOcean Spaces ou serviço
    storage_file_key = db.Column(db.String(500))  # Key no Spaces (docg/{org_id}/templates/{filename})
    file_size = db.Column(db.Integer)  # Tamanho em bytes
    file_mime_type = db.Column(db.String(100))  # MIME type do arquivo
    
    # Relationships
    creator = db.relationship('User', foreign_keys=[created_by])
    workflows = db.relationship('Workflow', backref='template', lazy='dynamic')
    documents = db.relationship('GeneratedDocument', backref='template', lazy='dynamic')
    
    def to_dict(self, include_tags=False):
        result = {
            'id': str(self.id),
            'organization_id': str(self.organization_id),
            'name': self.name,
            'description': self.description,
            'google_file_id': self.google_file_id,
            'google_file_type': self.google_file_type,
            'google_file_url': self.google_file_url,
            'microsoft_file_id': self.microsoft_file_id,
            'microsoft_file_type': self.microsoft_file_type,
            'thumbnail_url': self.thumbnail_url,
            'version': self.version,
            'last_synced_at': self.last_synced_at.isoformat() if self.last_synced_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'storage_type': self.storage_type,
            'storage_file_url': self.storage_file_url,
            'storage_file_key': self.storage_file_key,
            'file_size': self.file_size,
            'file_mime_type': self.file_mime_type
        }
        
        if include_tags:
            result['detected_tags'] = self.detected_tags or []
        
        return result

