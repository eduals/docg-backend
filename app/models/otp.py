"""
OTP (One-Time Password) Model
For email verification and password reset
"""
from app.database import db
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timedelta
import uuid
import random
import string


class OTP(db.Model):
    """
    OTP - One-Time Password for email verification and password reset
    """
    __tablename__ = 'otp'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # OTP data
    email = db.Column(db.String(255), nullable=False, index=True)
    code = db.Column(db.String(10), nullable=False)
    type = db.Column(db.String(50), nullable=False)  # EMAIL_VERIFICATION, PASSWORD_RESET

    # Expiration
    expires_at = db.Column(db.DateTime, nullable=False)

    # Usage tracking
    used = db.Column(db.Boolean, default=False, nullable=False)
    used_at = db.Column(db.DateTime)

    # Indexes
    __table_args__ = (
        db.Index('idx_otp_email', 'email'),
        db.Index('idx_otp_code', 'code'),
        db.Index('idx_otp_type', 'type'),
        db.Index('idx_otp_expires_at', 'expires_at'),
    )

    @staticmethod
    def generate_code(length=6):
        """Generate a random OTP code."""
        return ''.join(random.choices(string.digits, k=length))

    @staticmethod
    def create_otp(email, otp_type, ttl_minutes=10):
        """
        Create a new OTP for the given email.

        Args:
            email: Email address
            otp_type: Type of OTP (EMAIL_VERIFICATION, PASSWORD_RESET)
            ttl_minutes: Time to live in minutes (default: 10)

        Returns:
            OTP instance
        """
        code = OTP.generate_code()
        expires_at = datetime.utcnow() + timedelta(minutes=ttl_minutes)

        otp = OTP(
            id=uuid.uuid4(),
            email=email.lower().strip(),
            code=code,
            type=otp_type,
            expires_at=expires_at,
            used=False
        )

        db.session.add(otp)
        db.session.commit()

        return otp

    def is_valid(self):
        """Check if OTP is still valid."""
        if self.used:
            return False
        if datetime.utcnow() > self.expires_at:
            return False
        return True

    def mark_as_used(self):
        """Mark OTP as used."""
        self.used = True
        self.used_at = datetime.utcnow()
        db.session.commit()

    def to_dict(self):
        return {
            'id': str(self.id),
            'email': self.email,
            'type': self.type,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'used': self.used,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
