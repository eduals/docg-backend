from datetime import datetime, timedelta
from app.database import db
from sqlalchemy.dialects.postgresql import UUID
import uuid

# Account foi removido - migrado para Organization
# Mantido apenas para referência histórica durante migração

class FieldMapping(db.Model):
    """Mapeamento entre campos HubSpot e ClickSign"""
    __tablename__ = 'field_mappings'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    portal_id = db.Column(db.String(255), nullable=False, index=True)
    object_type = db.Column(db.String(50), nullable=False)  # 'contacts', 'deals', 'companies', 'tickets'
    clicksign_field_name = db.Column(db.String(255), nullable=False)
    clicksign_field_type = db.Column(db.String(50), nullable=False)  # 'text', 'email', 'date', etc
    hubspot_property_name = db.Column(db.String(255), nullable=False)
    hubspot_property_type = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    def to_dict(self):
        return {
            'id': self.id,
            'portal_id': self.portal_id,
            'object_type': self.object_type,
            'clicksign_field_name': self.clicksign_field_name,
            'clicksign_field_type': self.clicksign_field_type,
            'hubspot_property_name': self.hubspot_property_name,
            'hubspot_property_type': self.hubspot_property_type,
            'description': self.description,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self):
        return f'<FieldMapping {self.portal_id}:{self.object_type}:{self.clicksign_field_name}>'


class EnvelopeRelation(db.Model):
    """Relação entre objetos HubSpot e envelopes ClickSign"""
    __tablename__ = 'envelope_relations'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    portal_id = db.Column(db.String(255), nullable=False, index=True)
    hubspot_object_type = db.Column(db.String(50), nullable=False)
    hubspot_object_id = db.Column(db.String(255), nullable=False)
    clicksign_envelope_id = db.Column(db.String(255), nullable=False, index=True)
    envelope_name = db.Column(db.String(500), nullable=True)
    envelope_status = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Índice composto para busca rápida
    __table_args__ = (
        db.Index('idx_portal_object', 'portal_id', 'hubspot_object_type', 'hubspot_object_id'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'portal_id': self.portal_id,
            'hubspot_object_type': self.hubspot_object_type,
            'hubspot_object_id': self.hubspot_object_id,
            'clicksign_envelope_id': self.clicksign_envelope_id,
            'envelope_name': self.envelope_name,
            'envelope_status': self.envelope_status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self):
        return f'<EnvelopeRelation {self.portal_id}:{self.hubspot_object_type}:{self.hubspot_object_id}>'


class GoogleOAuthToken(db.Model):
    """Tokens OAuth do Google por organização"""
    __tablename__ = 'google_oauth_tokens'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = db.Column(UUID(as_uuid=True), db.ForeignKey('organizations.id'), unique=True, nullable=False, index=True)
    access_token = db.Column(db.Text, nullable=False)  # Será criptografado
    refresh_token = db.Column(db.Text, nullable=True)  # Será criptografado
    token_expiry = db.Column(db.DateTime, nullable=True)
    scope = db.Column(db.Text, nullable=True)
    connected_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    def to_dict(self, include_tokens=False):
        data = {
            'id': self.id,
            'organization_id': self.organization_id,
            'token_expiry': self.token_expiry.isoformat() if self.token_expiry else None,
            'scope': self.scope,
            'connected_at': self.connected_at.isoformat() if self.connected_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'is_expired': self.is_expired()
        }
        if include_tokens:
            data['access_token'] = self.access_token
            data['refresh_token'] = self.refresh_token
        return data
    
    def is_expired(self):
        """Verifica se o token expirou"""
        if not self.token_expiry:
            return True
        return datetime.utcnow() >= self.token_expiry
    
    def __repr__(self):
        return f'<GoogleOAuthToken {self.organization_id}>'


class GoogleDriveConfig(db.Model):
    """Configuração de pastas do Google Drive"""
    __tablename__ = 'google_drive_config'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = db.Column(UUID(as_uuid=True), db.ForeignKey('organizations.id'), unique=True, nullable=False, index=True)
    templates_folder_id = db.Column(db.String(255), nullable=True)
    library_folder_id = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    def to_dict(self):
        return {
            'id': self.id,
            'organization_id': self.organization_id,
            'templates_folder_id': self.templates_folder_id,
            'library_folder_id': self.library_folder_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self):
        return f'<GoogleDriveConfig {self.organization_id}>'


class EnvelopeExecutionLog(db.Model):
    """Logs de execução de criação de envelopes"""
    __tablename__ = 'envelope_execution_logs'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    portal_id = db.Column(db.String(255), nullable=False, index=True)
    execution_id = db.Column(db.String(36), nullable=False, index=True)
    envelope_id = db.Column(db.String(255), nullable=True)
    step_name = db.Column(db.String(255), nullable=False)
    step_status = db.Column(db.String(50), nullable=False)  # 'pending', 'in_progress', 'completed', 'error'
    step_message = db.Column(db.Text, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    step_order = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Índice composto para busca rápida
    __table_args__ = (
        db.Index('idx_execution_order', 'execution_id', 'step_order'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'portal_id': self.portal_id,
            'execution_id': self.execution_id,
            'envelope_id': self.envelope_id,
            'step_name': self.step_name,
            'step_status': self.step_status,
            'step_message': self.step_message,
            'error_message': self.error_message,
            'step_order': self.step_order,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self):
        return f'<EnvelopeExecutionLog {self.execution_id}:{self.step_name}>'


class RiscEvent(db.Model):
    """Eventos de segurança RISC recebidos do Google"""
    __tablename__ = 'risc_events'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    google_user_id = db.Column(db.String(255), nullable=False, index=True)
    event_type = db.Column(db.String(255), nullable=False)
    token_payload = db.Column(db.Text, nullable=True)  # JSON do payload do token
    processed = db.Column(db.Boolean, default=False, nullable=False)
    action_taken = db.Column(db.String(255), nullable=True)
    processed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Índice para busca por usuário e status
    __table_args__ = (
        db.Index('idx_risc_user_processed', 'google_user_id', 'processed'),
    )
    
    def to_dict(self):
        import json
        return {
            'id': self.id,
            'google_user_id': self.google_user_id,
            'event_type': self.event_type,
            'token_payload': json.loads(self.token_payload) if self.token_payload else None,
            'processed': self.processed,
            'action_taken': self.action_taken,
            'processed_at': self.processed_at.isoformat() if self.processed_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self):
        return f'<RiscEvent {self.google_user_id}:{self.event_type}>'