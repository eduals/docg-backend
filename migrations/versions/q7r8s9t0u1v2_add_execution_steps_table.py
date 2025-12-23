"""Add execution_steps table

Revision ID: q7r8s9t0u1v2
Revises: p7q8r9s0t1u2
Create Date: 2024-12-22

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'q7r8s9t0u1v2'
down_revision = 'p7q8r9s0t1u2'
branch_labels = None
depends_on = None


def upgrade():
    # Create execution_steps table
    op.create_table(
        'execution_steps',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('execution_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('step_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('step_type', sa.String(100), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('data_in', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('data_out', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_details', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('execution_time_ms', sa.Integer(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes
    op.create_index(
        'ix_execution_steps_execution_id',
        'execution_steps',
        ['execution_id']
    )
    op.create_index(
        'ix_execution_steps_step_id',
        'execution_steps',
        ['step_id']
    )
    op.create_index(
        'ix_execution_steps_status',
        'execution_steps',
        ['status']
    )
    op.create_index(
        'ix_execution_steps_execution_position',
        'execution_steps',
        ['execution_id', 'position']
    )

    # Add foreign key to workflow_executions
    op.create_foreign_key(
        'fk_execution_steps_execution_id',
        'execution_steps',
        'workflow_executions',
        ['execution_id'],
        ['id'],
        ondelete='CASCADE'
    )

    # Add foreign key to workflow_nodes
    op.create_foreign_key(
        'fk_execution_steps_step_id',
        'execution_steps',
        'workflow_nodes',
        ['step_id'],
        ['id'],
        ondelete='SET NULL'
    )


def downgrade():
    op.drop_constraint('fk_execution_steps_step_id', 'execution_steps', type_='foreignkey')
    op.drop_constraint('fk_execution_steps_execution_id', 'execution_steps', type_='foreignkey')
    op.drop_index('ix_execution_steps_execution_position', table_name='execution_steps')
    op.drop_index('ix_execution_steps_status', table_name='execution_steps')
    op.drop_index('ix_execution_steps_step_id', table_name='execution_steps')
    op.drop_index('ix_execution_steps_execution_id', table_name='execution_steps')
    op.drop_table('execution_steps')
