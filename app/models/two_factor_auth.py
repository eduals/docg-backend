"""
Two-Factor Authentication Model
For TOTP-based 2FA using Google Authenticator, Authy, etc.
"""
from app.database import db
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
import pyotp
import qrcode
import io
import base64


class TwoFactorAuth(db.Model):
    """
    TwoFactorAuth - TOTP secrets and backup codes for 2FA
    """
    __tablename__ = 'two_factor_auth'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # User relationship
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True)

    # TOTP secret (encrypted in production)
    secret = db.Column(db.String(32), nullable=False)

    # Status
    enabled = db.Column(db.Boolean, default=False, nullable=False)
    verified = db.Column(db.Boolean, default=False, nullable=False)

    # Backup codes (comma-separated, hashed in production)
    backup_codes = db.Column(db.Text)

    # Usage tracking
    last_used_at = db.Column(db.DateTime)

    # Relationship
    user = db.relationship('User', backref=db.backref('two_factor_auth', uselist=False))

    # Indexes
    __table_args__ = (
        db.Index('idx_2fa_user_id', 'user_id'),
    )

    @staticmethod
    def generate_secret():
        """Generate a random TOTP secret."""
        return pyotp.random_base32()

    @staticmethod
    def generate_backup_codes(count=10):
        """Generate backup codes for emergency access."""
        import secrets
        codes = []
        for _ in range(count):
            # Generate 8-character alphanumeric code
            code = ''.join(secrets.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789') for _ in range(8))
            codes.append(code)
        return codes

    @staticmethod
    def create_for_user(user_id):
        """
        Create 2FA setup for a user.

        Args:
            user_id: User ID

        Returns:
            TwoFactorAuth instance
        """
        # Check if already exists
        existing = TwoFactorAuth.query.filter_by(user_id=user_id).first()
        if existing:
            return existing

        secret = TwoFactorAuth.generate_secret()
        backup_codes = TwoFactorAuth.generate_backup_codes()

        two_fa = TwoFactorAuth(
            id=uuid.uuid4(),
            user_id=user_id,
            secret=secret,
            enabled=False,
            verified=False,
            backup_codes=','.join(backup_codes)
        )

        db.session.add(two_fa)
        db.session.commit()

        return two_fa

    def get_totp_uri(self, user_email):
        """
        Get TOTP provisioning URI for QR code.

        Args:
            user_email: User's email address

        Returns:
            Provisioning URI string
        """
        return pyotp.totp.TOTP(self.secret).provisioning_uri(
            name=user_email,
            issuer_name='Pipehub'
        )

    def get_qr_code_base64(self, user_email):
        """
        Generate QR code as base64 image.

        Args:
            user_email: User's email address

        Returns:
            Base64 encoded QR code image
        """
        uri = self.get_totp_uri(user_email)

        # Generate QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(uri)
        qr.make(fit=True)

        # Create image
        img = qr.make_image(fill_color="black", back_color="white")

        # Convert to base64
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        img_base64 = base64.b64encode(buffer.getvalue()).decode()

        return f"data:image/png;base64,{img_base64}"

    def verify_code(self, code):
        """
        Verify TOTP code or backup code.

        Args:
            code: 6-digit TOTP code or 8-character backup code

        Returns:
            True if code is valid
        """
        # Try TOTP code first
        totp = pyotp.TOTP(self.secret)
        if totp.verify(code, valid_window=1):  # Allow 30s drift
            self.last_used_at = datetime.utcnow()
            db.session.commit()
            return True

        # Try backup codes
        if self.backup_codes:
            codes = self.backup_codes.split(',')
            if code.upper() in codes:
                # Remove used backup code
                codes.remove(code.upper())
                self.backup_codes = ','.join(codes)
                self.last_used_at = datetime.utcnow()
                db.session.commit()
                return True

        return False

    def enable(self):
        """Enable 2FA for this user."""
        self.enabled = True
        self.verified = True
        db.session.commit()

    def disable(self):
        """Disable 2FA for this user."""
        self.enabled = False
        db.session.commit()

    def get_backup_codes(self):
        """Get list of remaining backup codes."""
        if not self.backup_codes:
            return []
        return self.backup_codes.split(',')

    def regenerate_backup_codes(self):
        """Generate new backup codes."""
        backup_codes = TwoFactorAuth.generate_backup_codes()
        self.backup_codes = ','.join(backup_codes)
        db.session.commit()
        return backup_codes

    def to_dict(self, include_secret=False):
        data = {
            'id': str(self.id),
            'user_id': str(self.user_id),
            'enabled': self.enabled,
            'verified': self.verified,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None,
        }

        if include_secret:
            data['secret'] = self.secret

        return data
