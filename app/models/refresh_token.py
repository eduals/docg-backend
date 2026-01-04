"""
Refresh Token Model
For JWT token refresh and session management
"""
from app.database import db
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timedelta
import uuid
import secrets


class RefreshToken(db.Model):
    """
    RefreshToken - Long-lived tokens for refreshing JWT access tokens
    """
    __tablename__ = 'refresh_token'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Token data
    token = db.Column(db.String(255), nullable=False, unique=True, index=True)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)

    # Expiration (default: 30 days)
    expires_at = db.Column(db.DateTime, nullable=False)

    # Revocation
    revoked = db.Column(db.Boolean, default=False, nullable=False)
    revoked_at = db.Column(db.DateTime)
    revoked_reason = db.Column(db.String(255))

    # Session tracking
    ip_address = db.Column(db.String(50))
    user_agent = db.Column(db.String(500))
    last_used_at = db.Column(db.DateTime)

    # Relationship
    user = db.relationship('User', backref=db.backref('refresh_tokens', lazy='dynamic'))

    # Indexes
    __table_args__ = (
        db.Index('idx_refresh_token_token', 'token'),
        db.Index('idx_refresh_token_user_id', 'user_id'),
        db.Index('idx_refresh_token_expires_at', 'expires_at'),
    )

    @staticmethod
    def generate_token():
        """Generate a cryptographically secure random token."""
        return secrets.token_urlsafe(64)

    @staticmethod
    def create_refresh_token(
        user_id,
        ip_address=None,
        user_agent=None,
        ttl_days=30
    ):
        """
        Create a new refresh token for a user.

        Args:
            user_id: User ID
            ip_address: IP address of the request
            user_agent: User agent string
            ttl_days: Time to live in days (default: 30)

        Returns:
            RefreshToken instance
        """
        token = RefreshToken.generate_token()
        expires_at = datetime.utcnow() + timedelta(days=ttl_days)

        refresh_token = RefreshToken(
            id=uuid.uuid4(),
            token=token,
            user_id=user_id,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
            revoked=False
        )

        db.session.add(refresh_token)
        db.session.commit()

        return refresh_token

    def is_valid(self):
        """Check if refresh token is still valid."""
        if self.revoked:
            return False
        if datetime.utcnow() > self.expires_at:
            return False
        return True

    def revoke(self, reason=None):
        """Revoke this refresh token."""
        self.revoked = True
        self.revoked_at = datetime.utcnow()
        self.revoked_reason = reason
        db.session.commit()

    def mark_used(self):
        """Mark token as recently used."""
        self.last_used_at = datetime.utcnow()
        db.session.commit()

    @staticmethod
    def revoke_all_for_user(user_id, reason=None):
        """Revoke all refresh tokens for a user."""
        tokens = RefreshToken.query.filter_by(user_id=user_id, revoked=False).all()
        for token in tokens:
            token.revoke(reason)

    @staticmethod
    def cleanup_expired():
        """Remove expired and revoked tokens (cleanup job)."""
        cutoff = datetime.utcnow() - timedelta(days=90)  # Keep for 90 days

        # Delete old expired tokens
        RefreshToken.query.filter(
            RefreshToken.expires_at < cutoff
        ).delete()

        # Delete old revoked tokens
        RefreshToken.query.filter(
            RefreshToken.revoked == True,
            RefreshToken.revoked_at < cutoff
        ).delete()

        db.session.commit()

    def to_dict(self):
        return {
            'id': str(self.id),
            'token': self.token,
            'user_id': str(self.user_id),
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'revoked': self.revoked,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None,
        }
