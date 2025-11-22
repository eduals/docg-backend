"""Add trial fields to organizations

Revision ID: a1b2c3d4e5f6
Revises: 0cd91583b371
Create Date: 2025-11-21 22:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '0cd91583b371'
branch_labels = None
depends_on = None


def upgrade():
    # Add trial and plan fields to organizations table
    op.add_column('organizations', sa.Column('trial_expires_at', sa.DateTime(), nullable=True))
    op.add_column('organizations', sa.Column('plan_expires_at', sa.DateTime(), nullable=True))
    op.add_column('organizations', sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('organizations', sa.Column('clicksign_api_key', sa.Text(), nullable=True))


def downgrade():
    # Remove columns
    op.drop_column('organizations', 'clicksign_api_key')
    op.drop_column('organizations', 'is_active')
    op.drop_column('organizations', 'plan_expires_at')
    op.drop_column('organizations', 'trial_expires_at')

