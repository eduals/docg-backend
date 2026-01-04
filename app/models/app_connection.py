"""
App Connection Models - Encrypted credentials for integrations
Based on Activepieces architecture
"""
from app.database import db
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime
import uuid
from enum import Enum


class AppConnectionType(str, Enum):
    """Type of app connection authentication"""
    OAUTH2 = "OAUTH2"
    PLATFORM_OAUTH2 = "PLATFORM_OAUTH2"  # OAuth managed by platform
    CLOUD_OAUTH2 = "CLOUD_OAUTH2"  # OAuth managed by cloud
    SECRET_TEXT = "SECRET_TEXT"  # API Key, Password, etc
    BASIC_AUTH = "BASIC_AUTH"  # Username + Password
    CUSTOM_AUTH = "CUSTOM_AUTH"  # Custom authentication
    NO_AUTH = "NO_AUTH"  # No authentication required


class AppConnectionStatus(str, Enum):
    """Status of app connection"""
    ACTIVE = "ACTIVE"
    ERROR = "ERROR"
    MISSING = "MISSING"


class AppConnection(db.Model):
    """
    App Connection - Encrypted credentials for app integrations
    Stores OAuth tokens, API keys, etc in encrypted JSONB
    """
    __tablename__ = 'app_connection'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Identification
    external_id = db.Column(db.String(255), nullable=False)  # User-defined ID
    display_name = db.Column(db.String(255), nullable=False)

    # Piece/App info
    piece_name = db.Column(db.String(100), nullable=False)  # "hubspot", "gmail", etc
    piece_version = db.Column(db.String(50), nullable=False)

    # Authentication type
    type = db.Column(db.String(50), nullable=False)  # OAUTH2, SECRET_TEXT, etc

    # Status
    status = db.Column(db.String(50), default='ACTIVE', nullable=False)  # ACTIVE, ERROR, MISSING

    # Ownership
    project_id = db.Column(UUID(as_uuid=True), db.ForeignKey('project.id', ondelete='CASCADE'), nullable=False)

    # Encrypted value (IMPORTANT: Always encrypted!)
    # Structure depends on type:
    # - OAUTH2: {access_token, refresh_token, expires_at, scope, ...}
    # - SECRET_TEXT: {api_key: "..."}
    # - BASIC_AUTH: {username: "...", password: "..."}
    # - CUSTOM_AUTH: {...}
    value = db.Column(JSONB, nullable=False)  # ENCRYPTED!

    # Relationships
    project = db.relationship('Project', back_populates='app_connections')

    # Indexes
    __table_args__ = (
        db.Index('idx_app_connection_project_id', 'project_id'),
        db.Index('idx_app_connection_piece_name', 'piece_name'),
        db.Index('idx_app_connection_external_id', 'external_id'),
    )

    def to_dict(self, include_value=False):
        """
        Serialize to dict
        By default, does NOT include encrypted value
        """
        data = {
            'id': str(self.id),
            'external_id': self.external_id,
            'display_name': self.display_name,
            'piece_name': self.piece_name,
            'piece_version': self.piece_version,
            'type': self.type,
            'status': self.status,
            'project_id': str(self.project_id),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

        if include_value:
            data['value'] = self.value

        return data


class ConnectionKey(db.Model):
    """
    Connection Key - Global OAuth app credentials
    Used for PLATFORM_OAUTH2 and CLOUD_OAUTH2
    """
    __tablename__ = 'connection_key'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # OAuth app info
    piece_name = db.Column(db.String(100), nullable=False, unique=True)  # "hubspot", "gmail"

    # OAuth credentials (encrypted)
    client_id = db.Column(db.String(512), nullable=False)
    client_secret = db.Column(db.String(512), nullable=False)  # ENCRYPTED

    # OAuth config
    redirect_uri = db.Column(db.String(512))
    scopes = db.Column(JSONB)  # ["scope1", "scope2"]

    # Platform scope (NULL for global, platform_id for platform-specific)
    platform_id = db.Column(UUID(as_uuid=True), db.ForeignKey('platform.id', ondelete='CASCADE'))

    def to_dict(self, include_secret=False):
        data = {
            'id': str(self.id),
            'piece_name': self.piece_name,
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'scopes': self.scopes,
            'platform_id': str(self.platform_id) if self.platform_id else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

        if include_secret:
            data['client_secret'] = self.client_secret

        return data
