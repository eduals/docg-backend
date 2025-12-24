"""Migrate to visual workflow format with nodes/edges JSONB

Revision ID: y4z5a6b7c8d9
Revises: x3y4z5a6b7c8
Create Date: 2025-12-24 12:00:00.000000

This migration:
1. Adds nodes, edges, visibility columns to workflows table
2. Removes legacy workflow fields (source_connection_id, template_id, etc)
3. Drops workflow_nodes, workflow_field_mappings, ai_generation_mappings tables
4. Updates foreign keys in execution_steps, signature_requests, workflow_approvals

BREAKING CHANGE: Existing workflows will be lost. No backward compatibility.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'y4z5a6b7c8d9'
down_revision = 'x3y4z5a6b7c8'
branch_labels = None
depends_on = None


def upgrade():
    # === 1. ADD new columns to workflows ===
    op.add_column('workflows', sa.Column('nodes', postgresql.JSONB, nullable=False, server_default='[]'))
    op.add_column('workflows', sa.Column('edges', postgresql.JSONB, nullable=False, server_default='[]'))
    op.add_column('workflows', sa.Column('visibility', sa.String(20), nullable=False, server_default='private'))

    # === 2. REMOVE legacy workflow columns ===
    op.drop_column('workflows', 'source_connection_id')
    op.drop_column('workflows', 'source_object_type')
    op.drop_column('workflows', 'source_config')
    op.drop_column('workflows', 'template_id')
    op.drop_column('workflows', 'output_folder_id')
    op.drop_column('workflows', 'output_name_template')
    op.drop_column('workflows', 'create_pdf')
    op.drop_column('workflows', 'trigger_type')
    op.drop_column('workflows', 'trigger_config')
    op.drop_column('workflows', 'post_actions')

    # === 3. UPDATE execution_steps: workflow_node_id (UUID FK) → node_id (String) ===
    # Drop FK constraint first (use IF EXISTS for safety)
    op.execute('ALTER TABLE execution_steps DROP CONSTRAINT IF EXISTS execution_steps_step_id_fkey')
    op.execute('ALTER TABLE execution_steps DROP CONSTRAINT IF EXISTS fk_execution_steps_step_id')

    # Drop old column and index
    op.execute('DROP INDEX IF EXISTS idx_execution_step_step_id')
    op.drop_column('execution_steps', 'step_id')

    # Add new column
    op.add_column('execution_steps', sa.Column('node_id', sa.String(255), nullable=True))
    op.create_index('idx_execution_step_node_id', 'execution_steps', ['node_id'])

    # === 4. UPDATE signature_requests: node_id (UUID FK) → node_id (String) ===
    # Drop FK constraint and relationship
    op.execute('ALTER TABLE signature_requests DROP CONSTRAINT IF EXISTS signature_requests_node_id_fkey')

    # Alter column type
    op.alter_column(
        'signature_requests',
        'node_id',
        type_=sa.String(255),
        existing_type=postgresql.UUID(as_uuid=True),
        existing_nullable=True,
        postgresql_using='node_id::text'
    )

    # === 5. UPDATE workflow_approvals: node_id (UUID FK) → node_id (String) ===
    # Drop FK constraint
    op.execute('ALTER TABLE workflow_approvals DROP CONSTRAINT IF EXISTS workflow_approvals_node_id_fkey')

    # Alter column type
    op.alter_column(
        'workflow_approvals',
        'node_id',
        type_=sa.String(255),
        existing_type=postgresql.UUID(as_uuid=True),
        existing_nullable=False,
        postgresql_using='node_id::text'
    )

    # === 6. UPDATE workflow_executions: current_node_id (UUID FK) → String ===
    # Drop FK constraint
    op.execute('ALTER TABLE workflow_executions DROP CONSTRAINT IF EXISTS workflow_executions_current_node_id_fkey')

    # Alter column type
    op.alter_column(
        'workflow_executions',
        'current_node_id',
        type_=sa.String(255),
        existing_type=postgresql.UUID(as_uuid=True),
        existing_nullable=True,
        postgresql_using='current_node_id::text'
    )

    # === 7. DROP legacy tables ===
    op.drop_table('workflow_nodes')
    op.drop_table('workflow_field_mappings')
    op.drop_table('ai_generation_mappings')


def downgrade():
    """
    Downgrade not supported - breaking change.

    This migration fundamentally changes the workflow structure from
    relational (workflow_nodes table) to JSONB (nodes/edges columns).

    Reverting would require data migration that is not feasible.
    """
    raise NotImplementedError(
        "Downgrade not supported for y4z5a6b7c8d9_visual_workflow_nodes_edges. "
        "This is a breaking change with no backward compatibility."
    )
