"""Create OTP table for email verification and password reset

Revision ID: bbb222ccc333
Revises: aaa111bbb222
Create Date: 2026-01-03 01:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'bbb222ccc333'
down_revision = 'aaa111bbb222'
branch_labels = None
depends_on = None


def upgrade():
    # Create OTP table
    op.create_table('otp',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('code', sa.String(length=10), nullable=False),
        sa.Column('type', sa.String(length=50), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('used', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('used_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes
    op.create_index('idx_otp_email', 'otp', ['email'], unique=False)
    op.create_index('idx_otp_code', 'otp', ['code'], unique=False)
    op.create_index('idx_otp_type', 'otp', ['type'], unique=False)
    op.create_index('idx_otp_expires_at', 'otp', ['expires_at'], unique=False)


def downgrade():
    # Drop indexes
    op.drop_index('idx_otp_expires_at', table_name='otp')
    op.drop_index('idx_otp_type', table_name='otp')
    op.drop_index('idx_otp_code', table_name='otp')
    op.drop_index('idx_otp_email', table_name='otp')

    # Drop table
    op.drop_table('otp')
