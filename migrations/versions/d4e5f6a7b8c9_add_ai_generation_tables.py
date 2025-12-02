"""Add AI generation tables

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2024-01-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from datetime import datetime

# revision identifiers, used by Alembic.
revision = 'd4e5f6a7b8c9'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def upgrade():
    # Criar tabela ai_generation_mappings
    op.create_table(
        'ai_generation_mappings',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('workflow_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workflows.id', ondelete='CASCADE'), nullable=False),
        sa.Column('ai_tag', sa.String(255), nullable=False),
        sa.Column('source_fields', postgresql.JSONB),
        sa.Column('provider', sa.String(50), nullable=False),
        sa.Column('model', sa.String(100), nullable=False),
        sa.Column('ai_connection_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('data_source_connections.id', ondelete='SET NULL')),
        sa.Column('prompt_template', sa.Text),
        sa.Column('temperature', sa.Float, server_default='0.7'),
        sa.Column('max_tokens', sa.Integer, server_default='1000'),
        sa.Column('fallback_value', sa.Text),
        sa.Column('last_used_at', sa.DateTime),
        sa.Column('usage_count', sa.Integer, server_default='0'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    
    # Índice único para workflow_id + ai_tag
    op.create_unique_constraint(
        'unique_workflow_ai_tag', 
        'ai_generation_mappings', 
        ['workflow_id', 'ai_tag']
    )
    
    # Índice para ai_connection_id
    op.create_index(
        'idx_ai_mapping_connection', 
        'ai_generation_mappings', 
        ['ai_connection_id']
    )
    
    # Índice para workflow_id
    op.create_index(
        'idx_ai_mapping_workflow', 
        'ai_generation_mappings', 
        ['workflow_id']
    )
    
    # Adicionar coluna ai_metrics em workflow_executions
    op.add_column(
        'workflow_executions', 
        sa.Column('ai_metrics', postgresql.JSONB)
    )


def downgrade():
    # Remover coluna ai_metrics
    op.drop_column('workflow_executions', 'ai_metrics')
    
    # Remover índices
    op.drop_index('idx_ai_mapping_workflow', table_name='ai_generation_mappings')
    op.drop_index('idx_ai_mapping_connection', table_name='ai_generation_mappings')
    op.drop_constraint('unique_workflow_ai_tag', 'ai_generation_mappings', type_='unique')
    
    # Remover tabela
    op.drop_table('ai_generation_mappings')

