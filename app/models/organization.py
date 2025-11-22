import uuid
from datetime import datetime
from app.database import db
from sqlalchemy.dialects.postgresql import UUID, JSONB

class Organization(db.Model):
    __tablename__ = 'organizations'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    plan = db.Column(db.String(50), default='free')  # free, starter, pro, enterprise
    documents_limit = db.Column(db.Integer, default=10)  # limite mensal
    documents_used = db.Column(db.Integer, default=0)
    users_limit = db.Column(db.Integer, default=1)
    billing_email = db.Column(db.String(255))
    stripe_customer_id = db.Column(db.String(255))
    stripe_subscription_id = db.Column(db.String(255))
    trial_expires_at = db.Column(db.DateTime, nullable=True)
    plan_expires_at = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    clicksign_api_key = db.Column(db.Text, nullable=True)  # Temporário - será migrado para DataSourceConnection
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    users = db.relationship('User', backref='organization', lazy='dynamic', cascade='all, delete-orphan')
    connections = db.relationship('DataSourceConnection', backref='organization', lazy='dynamic', cascade='all, delete-orphan')
    templates = db.relationship('Template', backref='organization', lazy='dynamic', cascade='all, delete-orphan')
    workflows = db.relationship('Workflow', backref='organization', lazy='dynamic', cascade='all, delete-orphan')
    documents = db.relationship('GeneratedDocument', backref='organization', lazy='dynamic', cascade='all, delete-orphan')
    features = db.relationship('OrganizationFeature', backref='organization', lazy='dynamic', cascade='all, delete-orphan')
    
    def can_generate_document(self):
        """Verifica se organização ainda tem quota disponível"""
        return self.documents_used < self.documents_limit
    
    def increment_document_count(self):
        """Incrementa contador de documentos usados"""
        self.documents_used += 1
        db.session.commit()
    
    def get_status(self):
        """Retorna o status da organização: 'trial', 'expired', ou 'active'"""
        now = datetime.utcnow()
        
        # Se não está ativa
        if not self.is_active:
            return 'expired'
        
        # Se tem plano ativo e não expirou
        if self.plan_expires_at and self.plan_expires_at > now:
            return 'active'
        
        # Se trial ainda está ativo
        if self.trial_expires_at and self.trial_expires_at > now:
            return 'trial'
        
        # Trial expirado e sem plano
        return 'expired'
    
    def to_dict(self, include_api_key=False):
        data = {
            'id': str(self.id),
            'name': self.name,
            'slug': self.slug,
            'plan': self.plan,
            'documents_limit': self.documents_limit,
            'documents_used': self.documents_used,
            'users_limit': self.users_limit,
            'billing_email': self.billing_email,
            'trial_expires_at': self.trial_expires_at.isoformat() if self.trial_expires_at else None,
            'plan_expires_at': self.plan_expires_at.isoformat() if self.plan_expires_at else None,
            'is_active': self.is_active,
            'status': self.get_status(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        if include_api_key:
            data['clicksign_api_key'] = self.clicksign_api_key
        
        return data


class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = db.Column(UUID(as_uuid=True), db.ForeignKey('organizations.id'), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(255))
    role = db.Column(db.String(50), default='user')  # admin, user
    hubspot_user_id = db.Column(db.String(100))
    google_user_id = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        db.UniqueConstraint('organization_id', 'email', name='unique_user_org_email'),
    )
    
    def is_admin(self):
        return self.role == 'admin'
    
    def can_create_workflow(self):
        return self.role == 'admin'
    
    def can_create_template(self):
        return self.role == 'admin'
    
    def to_dict(self):
        return {
            'id': str(self.id),
            'organization_id': str(self.organization_id),
            'email': self.email,
            'name': self.name,
            'role': self.role,
            'hubspot_user_id': self.hubspot_user_id,
            'google_user_id': self.google_user_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class OrganizationFeature(db.Model):
    __tablename__ = 'organization_features'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = db.Column(UUID(as_uuid=True), db.ForeignKey('organizations.id'), nullable=False)
    feature_name = db.Column(db.String(100), nullable=False)  # clicksign, docusign, etc.
    enabled = db.Column(db.Boolean, default=False)
    config = db.Column(JSONB)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        db.UniqueConstraint('organization_id', 'feature_name', name='unique_org_feature'),
    )
    
    def to_dict(self):
        return {
            'id': str(self.id),
            'organization_id': str(self.organization_id),
            'feature_name': self.feature_name,
            'enabled': self.enabled,
            'config': self.config,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

