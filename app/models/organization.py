import uuid
from datetime import datetime
from app.database import db
from sqlalchemy.dialects.postgresql import UUID, JSONB

class Organization(db.Model):
    __tablename__ = 'organizations'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    plan = db.Column(db.String(50), default='free')  # free, starter, pro, team, enterprise
    documents_limit = db.Column(db.Integer, default=10)  # limite mensal
    documents_used = db.Column(db.Integer, default=0)
    users_limit = db.Column(db.Integer, default=1)
    workflows_limit = db.Column(db.Integer, nullable=True)  # None = ilimitado
    workflows_used = db.Column(db.Integer, default=0)
    billing_email = db.Column(db.String(255))
    stripe_customer_id = db.Column(db.String(255))
    stripe_subscription_id = db.Column(db.String(255))
    trial_expires_at = db.Column(db.DateTime, nullable=True)
    plan_expires_at = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    onboarding_completed = db.Column(db.Boolean, default=False, nullable=False)
    onboarding_data = db.Column(JSONB)
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
        if self.documents_limit is None:
            return True
        return self.documents_used < self.documents_limit
    
    def increment_document_count(self):
        """Incrementa contador de documentos usados"""
        self.documents_used += 1
        db.session.commit()
    
    def can_create_workflow(self):
        """Verifica se pode criar novo workflow"""
        from app.models import Workflow
        if self.workflows_limit is None:
            return True
        current_count = Workflow.query.filter_by(organization_id=self.id).count()
        return current_count < self.workflows_limit
    
    def increment_workflow_count(self):
        """Incrementa contador de workflows (sem commit - commit deve ser feito externamente)"""
        self.workflows_used += 1
    
    def sync_workflows_count(self):
        """Sincroniza workflows_used com a contagem real do banco"""
        from app.models import Workflow
        real_count = Workflow.query.filter_by(organization_id=self.id).count()
        self.workflows_used = real_count
        db.session.commit()
    
    def update_plan_from_stripe(self, plan_name, subscription_data):
        """Atualiza organização com dados do plano do Stripe"""
        from app.services.stripe_service import PLAN_CONFIG
        
        config = PLAN_CONFIG.get(plan_name, {})
        self.plan = plan_name
        self.stripe_subscription_id = subscription_data.get('subscription_id')
        self.users_limit = config.get('users_limit')
        self.documents_limit = config.get('documents_limit')
        self.workflows_limit = config.get('workflows_limit')
        
        # Calcular plan_expires_at baseado no período da subscription
        if subscription_data.get('current_period_end'):
            from datetime import datetime
            self.plan_expires_at = datetime.fromtimestamp(subscription_data['current_period_end'])
        elif subscription_data.get('billing_cycle_anchor'):
            from datetime import datetime, timedelta
            # Assumir mensal por padrão
            self.plan_expires_at = datetime.fromtimestamp(subscription_data['billing_cycle_anchor']) + timedelta(days=30)
        
        self.is_active = True
        db.session.commit()
    
    def get_limits(self):
        """Retorna limites do plano atual"""
        return {
            'users': self.users_limit,
            'documents': self.documents_limit,
            'workflows': self.workflows_limit,
        }
    
    def get_usage(self):
        """Retorna uso atual"""
        from app.models import User, Workflow
        return {
            'users': User.query.filter_by(organization_id=self.id).count(),
            'documents': self.documents_used,
            'workflows': Workflow.query.filter_by(organization_id=self.id).count(),
        }
    
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
    
    def to_dict(self, include_api_key=False, include_limits=False):
        data = {
            'id': str(self.id),
            'name': self.name,
            'slug': self.slug,
            'plan': self.plan,
            'documents_limit': self.documents_limit,
            'documents_used': self.documents_used,
            'users_limit': self.users_limit,
            'workflows_limit': self.workflows_limit,
            'workflows_used': self.workflows_used,
            'billing_email': self.billing_email,
            'trial_expires_at': self.trial_expires_at.isoformat() if self.trial_expires_at else None,
            'plan_expires_at': self.plan_expires_at.isoformat() if self.plan_expires_at else None,
            'is_active': self.is_active,
            'onboarding_completed': self.onboarding_completed,
            'onboarding_data': self.onboarding_data,
            'status': self.get_status(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        if include_api_key:
            data['clicksign_api_key'] = self.clicksign_api_key
        
        if include_limits:
            data['limits'] = self.get_limits()
            data['usage'] = self.get_usage()
        
        return data


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = db.Column(UUID(as_uuid=True), db.ForeignKey('organizations.id'), nullable=True)
    email = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(255))  # Legacy field, use first_name + last_name
    role = db.Column(db.String(50), default='user')  # admin, user
    hubspot_user_id = db.Column(db.String(100))
    google_user_id = db.Column(db.String(100))

    # ActivePieces Authentication fields
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    password_hash = db.Column(db.String(255))  # For local auth
    verified = db.Column(db.Boolean, default=False)  # Email verified
    track_events = db.Column(db.Boolean, default=True)
    news_letter = db.Column(db.Boolean, default=False)

    # Better Auth fields
    email_verified = db.Column(db.Boolean, default=False)  # Deprecated, use 'verified'
    is_anonymous = db.Column(db.Boolean, default=False)
    image = db.Column(db.Text, nullable=True)

    # Platform/Project system (Activepieces-style)
    platform_id = db.Column(UUID(as_uuid=True), db.ForeignKey('platform.id', ondelete='SET NULL'))
    platform_role = db.Column(db.String(50))  # ADMIN, MEMBER, OPERATOR
    status = db.Column(db.String(50), default='ACTIVE')  # ACTIVE, INACTIVE
    identity_id = db.Column(db.String(255), unique=True)  # For SSO/Auth providers
    external_id = db.Column(db.String(255))  # External system ID
    last_active_date = db.Column(db.DateTime)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    platform = db.relationship('Platform', back_populates='users', foreign_keys=[platform_id])
    project_memberships = db.relationship('ProjectMember', back_populates='user', cascade='all, delete-orphan')

    __table_args__ = (
        db.UniqueConstraint('organization_id', 'email', name='unique_user_org_email'),
    )
    
    def is_admin(self):
        return self.role == 'admin'
    
    def can_create_workflow(self):
        return self.role == 'admin'
    
    def can_create_template(self):
        return self.role == 'admin'
    
    def to_dict(self, include_activepieces=True):
        """
        Return user data dict.

        Args:
            include_activepieces: If True, returns ActivePieces-compatible format
        """
        if include_activepieces:
            # ActivePieces format
            return {
                'id': str(self.id),
                'email': self.email,
                'firstName': self.first_name or self.name or '',
                'lastName': self.last_name or '',
                'verified': self.verified or self.email_verified or False,
                'platformRole': self.platform_role or 'MEMBER',
                'platformId': str(self.platform_id) if self.platform_id else None,
                'status': self.status or 'ACTIVE',
                'externalId': self.external_id,
                'trackEvents': self.track_events if self.track_events is not None else True,
                'newsLetter': self.news_letter if self.news_letter is not None else False,
                'created': self.created_at.isoformat() if self.created_at else None,
                'updated': self.updated_at.isoformat() if self.updated_at else None,
            }
        else:
            # Legacy format
            return {
                'id': str(self.id),
                'organization_id': str(self.organization_id) if self.organization_id else None,
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

