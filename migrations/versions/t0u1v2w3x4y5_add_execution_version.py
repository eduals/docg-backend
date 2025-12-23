"""Add version column to workflow_executions for optimistic locking

Revision ID: t0u1v2w3x4y5
Revises: s9t0u1v2w3x4
Create Date: 2024-12-22

Adds optimistic locking support to prevent concurrent workflow executions.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 't0u1v2w3x4y5'
down_revision = 's9t0u1v2w3x4'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'workflow_executions',
        sa.Column('version', sa.Integer(), nullable=False, server_default='1')
    )


def downgrade():
    op.drop_column('workflow_executions', 'version')
