"""Drop accounts table

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2025-11-21 23:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c3d4e5f6a7b8'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade():
    # Dropar tabela accounts após migração completa
    # ATENÇÃO: Execute o script de migração de dados antes de rodar esta migration
    op.drop_table('accounts')


def downgrade():
    # Recriar tabela accounts (apenas para rollback)
    op.create_table(
        'accounts',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('portal_id', sa.String(length=255), nullable=False),
        sa.Column('clicksign_api_key', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('trial_expires_at', sa.DateTime(), nullable=False),
        sa.Column('plan_expires_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_accounts_portal_id', 'accounts', ['portal_id'], unique=True)

