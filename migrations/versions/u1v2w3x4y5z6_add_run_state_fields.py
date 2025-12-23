"""Add run state fields to workflow_execution

Revision ID: u1v2w3x4y5z6
Revises: t0u1v2w3x4y5
Create Date: 2025-12-23

Adds comprehensive run state tracking fields to workflow_executions table.
Features implemented:
- F1: Run State (progress, current_step, errors, preflight, delivery/signature states)
- F14: Phase metrics and correlation_id
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# revision identifiers, used by Alembic.
revision = 'u1v2w3x4y5z6'
down_revision = 't0u1v2w3x4y5'
branch_labels = None
depends_on = None


def upgrade():
    # === Progresso e estado atual ===
    op.add_column(
        'workflow_executions',
        sa.Column('progress', sa.Integer(), nullable=False, server_default='0')
    )

    op.add_column(
        'workflow_executions',
        sa.Column('current_step', postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )

    # === Erros separados (humano/técnico) ===
    op.add_column(
        'workflow_executions',
        sa.Column('last_error_human', sa.Text(), nullable=True)
    )

    op.add_column(
        'workflow_executions',
        sa.Column('last_error_tech', sa.Text(), nullable=True)
    )

    # === Preflight ===
    op.add_column(
        'workflow_executions',
        sa.Column('preflight_summary', postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )

    # === Estados de delivery e signature ===
    op.add_column(
        'workflow_executions',
        sa.Column('delivery_state', sa.String(20), nullable=True)
    )

    op.add_column(
        'workflow_executions',
        sa.Column('signature_state', sa.String(20), nullable=True)
    )

    # === Ações recomendadas ===
    op.add_column(
        'workflow_executions',
        sa.Column('recommended_actions', postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )

    # === Phase metrics (F14) ===
    op.add_column(
        'workflow_executions',
        sa.Column('phase_metrics', postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )

    # === Correlation ID (F14) ===
    op.add_column(
        'workflow_executions',
        sa.Column('correlation_id', postgresql.UUID(as_uuid=True), nullable=True)
    )

    # Populate correlation_id for existing records
    op.execute("""
        UPDATE workflow_executions
        SET correlation_id = gen_random_uuid()
        WHERE correlation_id IS NULL
    """)

    # Make correlation_id not null after population
    op.alter_column('workflow_executions', 'correlation_id', nullable=False)


def downgrade():
    op.drop_column('workflow_executions', 'correlation_id')
    op.drop_column('workflow_executions', 'phase_metrics')
    op.drop_column('workflow_executions', 'recommended_actions')
    op.drop_column('workflow_executions', 'signature_state')
    op.drop_column('workflow_executions', 'delivery_state')
    op.drop_column('workflow_executions', 'preflight_summary')
    op.drop_column('workflow_executions', 'last_error_tech')
    op.drop_column('workflow_executions', 'last_error_human')
    op.drop_column('workflow_executions', 'current_step')
    op.drop_column('workflow_executions', 'progress')
