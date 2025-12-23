"""Create execution_logs table

Revision ID: v1w2x3y4z5a6
Revises: u1v2w3x4y5z6
Create Date: 2025-12-23

Feature 5: Logs Estruturados
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'v1w2x3y4z5a6'
down_revision = 'u1v2w3x4y5z6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'execution_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('execution_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('step_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('level', sa.String(10), nullable=False),
        sa.Column('domain', sa.String(50), nullable=False),
        sa.Column('message_human', sa.Text(), nullable=False),
        sa.Column('details_tech', sa.Text(), nullable=True),
        sa.Column('correlation_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(['execution_id'], ['workflow_executions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['step_id'], ['execution_steps.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )

    # Índices
    with op.batch_alter_table('execution_logs', schema=None) as batch_op:
        batch_op.create_index('idx_execution_logs_execution_id', ['execution_id'], unique=False)
        batch_op.create_index('idx_execution_logs_level', ['level'], unique=False)
        batch_op.create_index('idx_execution_logs_domain', ['domain'], unique=False)
        batch_op.create_index('idx_execution_logs_correlation_id', ['correlation_id'], unique=False)
        batch_op.create_index('idx_execution_logs_timestamp', ['timestamp'], unique=False)
        batch_op.create_index('idx_execution_logs_exec_level', ['execution_id', 'level'], unique=False)
        batch_op.create_index('idx_execution_logs_exec_domain', ['execution_id', 'domain'], unique=False)


def downgrade():
    op.drop_table('execution_logs')
