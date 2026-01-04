"""
Permission System Models
Two-level permission system: Platform and Project
Based on Activepieces architecture
"""
from app.database import db
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from datetime import datetime
import uuid
from enum import Enum


class PlatformRole(str, Enum):
    """Platform-level roles"""
    ADMIN = "ADMIN"  # Full control over platform
    MEMBER = "MEMBER"  # Access only to invited projects
    OPERATOR = "OPERATOR"  # Auto-access to all non-private projects


class DefaultProjectRole(str, Enum):
    """Default project roles"""
    ADMIN = "Admin"
    EDITOR = "Editor"
    OPERATOR = "Operator"
    VIEWER = "Viewer"


class RoleType(str, Enum):
    """Type of role"""
    DEFAULT = "DEFAULT"  # System default role
    CUSTOM = "CUSTOM"  # Custom role created by admin


class Permission(str, Enum):
    """Granular permissions (28 total)"""
    # App Connections
    READ_APP_CONNECTION = "READ_APP_CONNECTION"
    WRITE_APP_CONNECTION = "WRITE_APP_CONNECTION"

    # Flows
    READ_FLOW = "READ_FLOW"
    WRITE_FLOW = "WRITE_FLOW"
    UPDATE_FLOW_STATUS = "UPDATE_FLOW_STATUS"

    # Invitations
    READ_INVITATION = "READ_INVITATION"
    WRITE_INVITATION = "WRITE_INVITATION"

    # Project Members
    READ_PROJECT_MEMBER = "READ_PROJECT_MEMBER"
    WRITE_PROJECT_MEMBER = "WRITE_PROJECT_MEMBER"

    # Project Releases
    READ_PROJECT_RELEASE = "READ_PROJECT_RELEASE"
    WRITE_PROJECT_RELEASE = "WRITE_PROJECT_RELEASE"

    # Runs
    READ_RUN = "READ_RUN"
    WRITE_RUN = "WRITE_RUN"

    # Folders
    READ_FOLDER = "READ_FOLDER"
    WRITE_FOLDER = "WRITE_FOLDER"

    # Alerts
    READ_ALERT = "READ_ALERT"
    WRITE_ALERT = "WRITE_ALERT"

    # MCP
    READ_MCP = "READ_MCP"
    WRITE_MCP = "WRITE_MCP"

    # Project
    READ_PROJECT = "READ_PROJECT"
    WRITE_PROJECT = "WRITE_PROJECT"

    # Todos
    READ_TODOS = "READ_TODOS"
    WRITE_TODOS = "WRITE_TODOS"

    # Tables
    READ_TABLE = "READ_TABLE"
    WRITE_TABLE = "WRITE_TABLE"


# Role permissions mapping (from Activepieces access-control-list.ts)
ROLE_PERMISSIONS = {
    DefaultProjectRole.ADMIN: [
        # All permissions
        Permission.READ_APP_CONNECTION,
        Permission.WRITE_APP_CONNECTION,
        Permission.READ_FLOW,
        Permission.WRITE_FLOW,
        Permission.UPDATE_FLOW_STATUS,
        Permission.READ_PROJECT_MEMBER,
        Permission.WRITE_PROJECT_MEMBER,
        Permission.WRITE_INVITATION,
        Permission.READ_INVITATION,
        Permission.WRITE_PROJECT_RELEASE,
        Permission.READ_PROJECT_RELEASE,
        Permission.READ_RUN,
        Permission.WRITE_RUN,
        Permission.WRITE_ALERT,
        Permission.READ_ALERT,
        Permission.WRITE_PROJECT,
        Permission.READ_PROJECT,
        Permission.WRITE_FOLDER,
        Permission.READ_FOLDER,
        Permission.READ_TODOS,
        Permission.WRITE_TODOS,
        Permission.READ_TABLE,
        Permission.WRITE_TABLE,
        Permission.READ_MCP,
        Permission.WRITE_MCP,
    ],
    DefaultProjectRole.EDITOR: [
        # Can edit everything but not manage members/invitations
        Permission.READ_APP_CONNECTION,
        Permission.WRITE_APP_CONNECTION,
        Permission.READ_FLOW,
        Permission.WRITE_FLOW,
        Permission.UPDATE_FLOW_STATUS,
        Permission.READ_PROJECT_MEMBER,
        Permission.READ_INVITATION,
        Permission.WRITE_PROJECT_RELEASE,
        Permission.READ_PROJECT_RELEASE,
        Permission.READ_RUN,
        Permission.WRITE_RUN,
        Permission.READ_PROJECT,
        Permission.WRITE_FOLDER,
        Permission.READ_FOLDER,
        Permission.READ_TODOS,
        Permission.WRITE_TODOS,
        Permission.READ_TABLE,
        Permission.WRITE_TABLE,
        Permission.READ_MCP,
        Permission.WRITE_MCP,
    ],
    DefaultProjectRole.OPERATOR: [
        # Can operate (start/stop flows) but not edit structure
        Permission.READ_APP_CONNECTION,
        Permission.WRITE_APP_CONNECTION,
        Permission.READ_FLOW,
        Permission.UPDATE_FLOW_STATUS,
        Permission.READ_PROJECT_MEMBER,
        Permission.READ_INVITATION,
        Permission.READ_PROJECT_RELEASE,
        Permission.READ_RUN,
        Permission.WRITE_RUN,
        Permission.READ_PROJECT,
        Permission.READ_FOLDER,
        Permission.READ_TODOS,
        Permission.WRITE_TODOS,
        Permission.READ_TABLE,
        Permission.READ_MCP,
    ],
    DefaultProjectRole.VIEWER: [
        # Read-only
        Permission.READ_APP_CONNECTION,
        Permission.READ_FLOW,
        Permission.READ_PROJECT_MEMBER,
        Permission.READ_INVITATION,
        Permission.READ_PROJECT,
        Permission.READ_RUN,
        Permission.READ_FOLDER,
        Permission.READ_TODOS,
        Permission.READ_TABLE,
        Permission.READ_MCP,
    ],
}


class ProjectRole(db.Model):
    """
    Project Role - Defines permissions for project members
    Can be DEFAULT (system) or CUSTOM (user-created)
    """
    __tablename__ = 'project_role'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Identification
    name = db.Column(db.String(255), nullable=False)  # "Admin", "Editor", "Custom Developer"

    # Type
    type = db.Column(db.String(50), nullable=False)  # DEFAULT or CUSTOM

    # Permissions - PostgreSQL array
    permissions = db.Column(ARRAY(db.String), nullable=False)

    # Scope - NULL for default roles, platform_id for custom roles
    platform_id = db.Column(UUID(as_uuid=True), db.ForeignKey('platform.id', ondelete='CASCADE'))

    # Relationships
    platform = db.relationship('Platform', back_populates='project_roles')
    members = db.relationship('ProjectMember', back_populates='project_role')
    user_invitations = db.relationship('UserInvitation', back_populates='project_role')

    # Indexes
    __table_args__ = (
        db.Index('idx_project_role_platform_id', 'platform_id'),
        db.Index('idx_project_role_type', 'type'),
    )

    def to_dict(self):
        return {
            'id': str(self.id),
            'name': self.name,
            'type': self.type,
            'permissions': self.permissions,
            'platform_id': str(self.platform_id) if self.platform_id else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class ProjectMember(db.Model):
    """
    Project Member - Links user to project with a role
    """
    __tablename__ = 'project_member'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    project_id = db.Column(UUID(as_uuid=True), db.ForeignKey('project.id', ondelete='CASCADE'), nullable=False)
    project_role_id = db.Column(UUID(as_uuid=True), db.ForeignKey('project_role.id', ondelete='CASCADE'), nullable=False)
    platform_id = db.Column(UUID(as_uuid=True), nullable=False)

    # Relationships
    user = db.relationship('User', back_populates='project_memberships')
    project = db.relationship('Project', back_populates='members')
    project_role = db.relationship('ProjectRole', back_populates='members')

    # Constraints and Indexes
    __table_args__ = (
        db.UniqueConstraint('user_id', 'project_id', 'platform_id', name='uk_project_member_user_project'),
        db.Index('idx_project_member_user_id', 'user_id'),
        db.Index('idx_project_member_project_id', 'project_id'),
        db.Index('idx_project_member_role_id', 'project_role_id'),
    )

    def to_dict(self):
        return {
            'id': str(self.id),
            'user_id': str(self.user_id),
            'project_id': str(self.project_id),
            'project_role_id': str(self.project_role_id),
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class InvitationType(str, Enum):
    """Type of invitation"""
    PLATFORM = "PLATFORM"  # Invite to entire platform
    PROJECT = "PROJECT"  # Invite to specific project


class InvitationStatus(str, Enum):
    """Status of invitation"""
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"


class UserInvitation(db.Model):
    """
    User Invitation - Invite users to platform or projects
    Two types:
    - PLATFORM: Invite to entire platform with platform_role
    - PROJECT: Invite to specific project with project_role
    """
    __tablename__ = 'user_invitation'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Email of invitee
    email = db.Column(db.String(255), nullable=False, index=True)

    # Status
    status = db.Column(db.String(50), nullable=False, default='PENDING')  # PENDING, ACCEPTED

    # Type (PLATFORM or PROJECT)
    type = db.Column(db.String(50), nullable=False)

    # Platform (always present)
    platform_id = db.Column(UUID(as_uuid=True), db.ForeignKey('platform.id', ondelete='CASCADE'), nullable=False)

    # If type = PLATFORM
    platform_role = db.Column(db.String(50))  # ADMIN, MEMBER, OPERATOR

    # If type = PROJECT
    project_id = db.Column(UUID(as_uuid=True), db.ForeignKey('project.id', ondelete='CASCADE'))
    project_role_id = db.Column(UUID(as_uuid=True), db.ForeignKey('project_role.id', ondelete='CASCADE'))

    # Relationships
    platform = db.relationship('Platform', back_populates='user_invitations')
    project = db.relationship('Project')
    project_role = db.relationship('ProjectRole', back_populates='user_invitations')

    # Constraints and Indexes
    __table_args__ = (
        db.UniqueConstraint('email', 'platform_id', 'project_id', name='uk_user_invitation_email_platform_project'),
        db.CheckConstraint(
            "(type = 'PLATFORM' AND platform_role IS NOT NULL AND project_id IS NULL AND project_role_id IS NULL) OR "
            "(type = 'PROJECT' AND platform_role IS NULL AND project_id IS NOT NULL AND project_role_id IS NOT NULL)",
            name='ck_user_invitation_type_fields'
        ),
        db.Index('idx_user_invitation_email', 'email'),
        db.Index('idx_user_invitation_status', 'status'),
        db.Index('idx_user_invitation_platform_id', 'platform_id'),
        db.Index('idx_user_invitation_project_id', 'project_id'),
    )

    def to_dict(self):
        return {
            'id': str(self.id),
            'email': self.email,
            'status': self.status,
            'type': self.type,
            'platform_id': str(self.platform_id),
            'platform_role': self.platform_role,
            'project_id': str(self.project_id) if self.project_id else None,
            'project_role_id': str(self.project_role_id) if self.project_role_id else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
