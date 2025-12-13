"""Add workflows_limit and onboarding fields to organizations

Revision ID: n4o5p6q7r8s9
Revises: m3n4o5p6q7r8
Create Date: 2025-01-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'n4o5p6q7r8s9'
down_revision = 'm3n4o5p6q7r8'
branch_labels = None
depends_on = None


def upgrade():
    # Adicionar campos de workflows e onboarding
    with op.batch_alter_table('organizations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('workflows_limit', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('workflows_used', sa.Integer(), server_default='0', nullable=False))
        batch_op.add_column(sa.Column('onboarding_completed', sa.Boolean(), server_default='false', nullable=False))
        batch_op.add_column(sa.Column('onboarding_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade():
    # Remover campos adicionados
    with op.batch_alter_table('organizations', schema=None) as batch_op:
        batch_op.drop_column('onboarding_data')
        batch_op.drop_column('onboarding_completed')
        batch_op.drop_column('workflows_used')
        batch_op.drop_column('workflows_limit')
