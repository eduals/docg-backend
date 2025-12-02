"""Add PKCE verifiers table for OAuth

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2024-12-01 19:50:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from datetime import datetime

# revision identifiers, used by Alembic.
revision = 'e5f6a7b8c9d0'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


def upgrade():
    # Criar tabela pkce_verifiers
    op.create_table(
        'pkce_verifiers',
        sa.Column('state', sa.String(255), primary_key=True, nullable=False),
        sa.Column('code_verifier', sa.Text, nullable=False),
        sa.Column('expires_at', sa.DateTime, nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    
    # Índice para expires_at para limpeza eficiente
    op.create_index(
        'idx_pkce_expires_at',
        'pkce_verifiers',
        ['expires_at']
    )
    
    # Índice para state (já é primary key, mas útil para queries)
    op.create_index(
        'idx_pkce_state',
        'pkce_verifiers',
        ['state']
    )


def downgrade():
    # Remover índices
    op.drop_index('idx_pkce_state', table_name='pkce_verifiers')
    op.drop_index('idx_pkce_expires_at', table_name='pkce_verifiers')
    
    # Remover tabela
    op.drop_table('pkce_verifiers')

