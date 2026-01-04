"""
Platform and Project Models - Multi-tenant structure
Based on Activepieces architecture
"""
from app.database import db
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime
import uuid


class Platform(db.Model):
    """
    Platform - Represents entire installation/tenant
    Equivalent to Organization but with more features
    """
    __tablename__ = 'platform'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Identification
    name = db.Column(db.String(255), nullable=False)
    external_id = db.Column(db.String(255), unique=True)  # Customer ID, etc

    # Branding
    branding_logo = db.Column(db.String(512))  # Logo URL
    branding_primary_color = db.Column(db.String(7))  # #RRGGBB
    branding_full_logo_url = db.Column(db.String(512))

    # SSO Configuration
    sso_enabled = db.Column(db.Boolean, default=False)
    sso_provider = db.Column(db.String(50))  # SAML, OIDC, Google, Microsoft
    sso_config = db.Column(JSONB)  # Provider-specific config

    # Piece/App Filtering
    filter_pieces_enabled = db.Column(db.Boolean, default=False)
    allowed_pieces = db.Column(JSONB)  # ["hubspot", "gmail", ...]
    blocked_pieces = db.Column(JSONB)

    # Limits and Quotas
    plan_type = db.Column(db.String(50), default='free')  # free, pro, enterprise
    max_projects = db.Column(db.Integer)
    max_flows = db.Column(db.Integer)
    max_runs_per_month = db.Column(db.Integer)

    # Status
    status = db.Column(db.String(50), default='active')  # active, suspended, deleted

    # Relationships
    projects = db.relationship('Project', back_populates='platform', cascade='all, delete-orphan')
    users = db.relationship('User', back_populates='platform', foreign_keys='User.platform_id')
    project_roles = db.relationship('ProjectRole', back_populates='platform', cascade='all, delete-orphan')
    user_invitations = db.relationship('UserInvitation', back_populates='platform', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': str(self.id),
            'name': self.name,
            'external_id': self.external_id,
            'plan_type': self.plan_type,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class Project(db.Model):
    """
    Project - Workspace within a Platform
    Users are added to projects with specific roles
    """
    __tablename__ = 'project'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Identification
    name = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(255), nullable=False)
    external_id = db.Column(db.String(255))  # For external system mapping

    # Ownership
    platform_id = db.Column(UUID(as_uuid=True), db.ForeignKey('platform.id', ondelete='CASCADE'), nullable=False)
    owner_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id', ondelete='SET NULL'))

    # Privacy
    is_private = db.Column(db.Boolean, default=False)  # If true, only members can access

    # Limits (inherited from platform but can be customized)
    max_flows = db.Column(db.Integer)
    max_runs_per_month = db.Column(db.Integer)

    # Relationships
    platform = db.relationship('Platform', back_populates='projects')
    owner = db.relationship('User', foreign_keys=[owner_id])
    members = db.relationship('ProjectMember', back_populates='project', cascade='all, delete-orphan')
    flows = db.relationship('Flow', back_populates='project', cascade='all, delete-orphan')
    folders = db.relationship('Folder', back_populates='project', cascade='all, delete-orphan')
    app_connections = db.relationship('AppConnection', back_populates='project', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': str(self.id),
            'name': self.name,
            'display_name': self.display_name,
            'platform_id': str(self.platform_id),
            'owner_id': str(self.owner_id) if self.owner_id else None,
            'is_private': self.is_private,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class Folder(db.Model):
    """
    Folder - Organize flows within a project
    """
    __tablename__ = 'folder'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Identification
    name = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(255), nullable=False)

    # Ownership
    project_id = db.Column(UUID(as_uuid=True), db.ForeignKey('project.id', ondelete='CASCADE'), nullable=False)

    # Relationships
    project = db.relationship('Project', back_populates='folders')
    flows = db.relationship('Flow', back_populates='folder')

    def to_dict(self):
        return {
            'id': str(self.id),
            'name': self.name,
            'display_name': self.display_name,
            'project_id': str(self.project_id),
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
