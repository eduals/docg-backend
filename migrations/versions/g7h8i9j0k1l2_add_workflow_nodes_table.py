"""Add workflow_nodes table

Revision ID: g7h8i9j0k1l2
Revises: f6a7b8c9d0e1
Create Date: 2025-12-05 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from datetime import datetime

# revision identifiers, used by Alembic.
revision = 'g7h8i9j0k1l2'
down_revision = 'f6a7b8c9d0e1'
branch_labels = None
depends_on = None


def upgrade():
    # Criar tabela workflow_nodes
    op.create_table(
        'workflow_nodes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('workflow_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workflows.id', ondelete='CASCADE'), nullable=False),
        sa.Column('node_type', sa.String(50), nullable=False),
        sa.Column('position', sa.Integer, nullable=False),
        sa.Column('parent_node_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workflow_nodes.id', ondelete='SET NULL')),
        sa.Column('config', postgresql.JSONB),
        sa.Column('status', sa.String(50), server_default='draft'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    
    # Índice único para workflow_id + position
    op.create_unique_constraint(
        'unique_workflow_position', 
        'workflow_nodes', 
        ['workflow_id', 'position']
    )
    
    # Índices para performance
    op.create_index(
        'idx_workflow_node_workflow', 
        'workflow_nodes', 
        ['workflow_id']
    )
    
    op.create_index(
        'idx_workflow_node_position', 
        'workflow_nodes', 
        ['workflow_id', 'position']
    )


def downgrade():
    # Remover índices
    op.drop_index('idx_workflow_node_position', table_name='workflow_nodes')
    op.drop_index('idx_workflow_node_workflow', table_name='workflow_nodes')
    op.drop_constraint('unique_workflow_position', 'workflow_nodes', type_='unique')
    
    # Remover tabela
    op.drop_table('workflow_nodes')
