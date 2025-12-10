"""add frontend_redirect_uri to pkce_verifiers

Revision ID: i9j0k1l2m3n4
Revises: h8i9j0k1l2m3
Create Date: 2025-12-05 17:50:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'i9j0k1l2m3n4'
down_revision = 'h8i9j0k1l2m3'
branch_labels = None
depends_on = None


def upgrade():
    # Adicionar coluna frontend_redirect_uri à tabela pkce_verifiers
    op.add_column('pkce_verifiers', sa.Column('frontend_redirect_uri', sa.String(length=500), nullable=True))


def downgrade():
    # Remover coluna frontend_redirect_uri da tabela pkce_verifiers
    op.drop_column('pkce_verifiers', 'frontend_redirect_uri')
