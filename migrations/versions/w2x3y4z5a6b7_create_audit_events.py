"""Create audit_events table

Revision ID: w2x3y4z5a6b7
Revises: v1w2x3y4z5a6
Create Date: 2025-12-23

Feature 6: Auditoria Append-Only
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'w2x3y4z5a6b7'
down_revision = 'v1w2x3y4z5a6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'audit_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('actor_type', sa.String(20), nullable=False),
        sa.Column('actor_id', sa.String(255), nullable=True),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('target_type', sa.String(50), nullable=False),
        sa.Column('target_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('event_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Índices
    with op.batch_alter_table('audit_events', schema=None) as batch_op:
        batch_op.create_index('idx_audit_events_org_target', ['organization_id', 'target_type', 'target_id'], unique=False)
        batch_op.create_index('idx_audit_events_timestamp', ['timestamp'], unique=False)
        batch_op.create_index('idx_audit_events_action', ['action'], unique=False)


def downgrade():
    op.drop_table('audit_events')
