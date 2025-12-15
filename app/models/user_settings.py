import uuid
from datetime import datetime
from app.database import db
from sqlalchemy.dialects.postgresql import UUID, JSONB


class UserPreference(db.Model):
    """Preferências do usuário (idioma, formato de data, timezone, etc.)"""
    __tablename__ = 'user_preferences'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False, unique=True)
    language = db.Column(db.String(10), default='pt')
    date_format = db.Column(db.String(20), default='DD/MM/YYYY')
    time_format = db.Column(db.String(10), default='24h')
    timezone = db.Column(db.String(100), default='America/Sao_Paulo')
    units = db.Column(db.String(20), default='metric')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': str(self.id),
            'user_id': str(self.user_id),
            'language': self.language,
            'date_format': self.date_format,
            'time_format': self.time_format,
            'timezone': self.timezone,
            'units': self.units,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self):
        return f'<UserPreference {self.user_id}>'


class UserNotificationPreference(db.Model):
    """Preferências de notificação por email do usuário"""
    __tablename__ = 'user_notification_preferences'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False, unique=True)
    email_enabled = db.Column(db.Boolean, default=True)
    email_document_generated = db.Column(db.Boolean, default=True)
    email_document_signed = db.Column(db.Boolean, default=True)
    email_workflow_executed = db.Column(db.Boolean, default=True)
    email_workflow_failed = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': str(self.id),
            'user_id': str(self.user_id),
            'email_enabled': self.email_enabled,
            'email_document_generated': self.email_document_generated,
            'email_document_signed': self.email_document_signed,
            'email_workflow_executed': self.email_workflow_executed,
            'email_workflow_failed': self.email_workflow_failed,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self):
        return f'<UserNotificationPreference {self.user_id}>'


class UserSession(db.Model):
    """Sessões ativas do usuário"""
    __tablename__ = 'user_sessions'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False)
    session_token = db.Column(db.String(255), unique=True, nullable=False)  # Hash do token
    ip_address = db.Column(db.String(45))  # IPv6 suporta até 45 caracteres
    user_agent = db.Column(db.Text)
    last_activity = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime)
    
    # Index para busca rápida
    __table_args__ = (
        db.Index('idx_user_sessions_user_id', 'user_id'),
        db.Index('idx_user_sessions_token', 'session_token'),
    )
    
    def to_dict(self):
        return {
            'id': str(self.id),
            'user_id': str(self.user_id),
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'last_activity': self.last_activity.isoformat() if self.last_activity else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None
        }
    
    def __repr__(self):
        return f'<UserSession {self.user_id}:{self.id}>'


class LoginHistory(db.Model):
    """Histórico de login do usuário"""
    __tablename__ = 'login_history'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    login_method = db.Column(db.String(50))  # 'oauth_google', 'oauth_microsoft', 'email', 'api_key'
    success = db.Column(db.Boolean, default=True)
    failure_reason = db.Column(db.String(255))  # Se success=False
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Index para busca rápida
    __table_args__ = (
        db.Index('idx_login_history_user_id', 'user_id'),
        db.Index('idx_login_history_created_at', 'created_at'),
    )
    
    def to_dict(self):
        return {
            'id': str(self.id),
            'user_id': str(self.user_id),
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'login_method': self.login_method,
            'success': self.success,
            'failure_reason': self.failure_reason,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self):
        return f'<LoginHistory {self.user_id}:{self.created_at}>'


class UserTwoFactorAuth(db.Model):
    """Configuração de autenticação de dois fatores do usuário"""
    __tablename__ = 'user_2fa'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False, unique=True)
    enabled = db.Column(db.Boolean, default=False)
    secret = db.Column(db.String(255))  # Secret para TOTP (criptografado)
    backup_codes = db.Column(JSONB)  # Códigos de backup (criptografados)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self, include_secret=False, include_backup_codes=False):
        data = {
            'id': str(self.id),
            'user_id': str(self.user_id),
            'enabled': self.enabled,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        if include_secret:
            data['secret'] = self.secret
        if include_backup_codes:
            data['backup_codes'] = self.backup_codes
        return data
    
    def __repr__(self):
        return f'<UserTwoFactorAuth {self.user_id}:{self.enabled}>'


class ApiKey(db.Model):
    """API keys do usuário"""
    __tablename__ = 'api_keys'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False)
    organization_id = db.Column(UUID(as_uuid=True), db.ForeignKey('organizations.id'), nullable=False)
    key_prefix = db.Column(db.String(10), nullable=False)  # 'dg_' prefix
    key_hash = db.Column(db.String(255), unique=True, nullable=False)  # Hash da chave completa
    name = db.Column(db.String(255))  # Nome descritivo dado pelo usuário
    last_used_at = db.Column(db.DateTime)
    expires_at = db.Column(db.DateTime, nullable=True)  # None = nunca expira
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Index
    __table_args__ = (
        db.Index('idx_api_keys_user_id', 'user_id'),
        db.Index('idx_api_keys_org_id', 'organization_id'),
    )
    
    def to_dict(self):
        return {
            'id': str(self.id),
            'user_id': str(self.user_id),
            'organization_id': str(self.organization_id),
            'key_prefix': self.key_prefix,
            'name': self.name,
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self):
        return f'<ApiKey {self.user_id}:{self.key_prefix}...>'


class GlobalFieldMapping(db.Model):
    """Mapeamentos globais de campos (não específicos de workflow)"""
    __tablename__ = 'global_field_mappings'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = db.Column(UUID(as_uuid=True), db.ForeignKey('organizations.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    source_system = db.Column(db.String(50), nullable=False)  # 'hubspot', 'google_drive', etc.
    target_system = db.Column(db.String(50), nullable=False)  # 'google_docs', 'microsoft_word', etc.
    mappings = db.Column(JSONB, nullable=False)  # Array de mapeamentos
    is_template = db.Column(db.Boolean, default=False)
    created_by = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': str(self.id),
            'organization_id': str(self.organization_id),
            'name': self.name,
            'source_system': self.source_system,
            'target_system': self.target_system,
            'mappings': self.mappings,
            'is_template': self.is_template,
            'created_by': str(self.created_by) if self.created_by else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self):
        return f'<GlobalFieldMapping {self.organization_id}:{self.name}>'
