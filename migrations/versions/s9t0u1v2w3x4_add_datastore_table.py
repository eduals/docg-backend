"""Add workflow_datastores table

Revision ID: s9t0u1v2w3x4
Revises: r8s9t0u1v2w3
Create Date: 2024-12-22

Adds persistent key-value storage for workflows.
Supports organization, workflow, and execution scopes with optional TTL.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 's9t0u1v2w3x4'
down_revision = 'r8s9t0u1v2w3'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'workflow_datastores',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            'organization_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('organizations.id', ondelete='CASCADE'),
            nullable=False
        ),
        sa.Column('scope', sa.String(50), nullable=False, server_default='organization'),
        sa.Column('scope_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('key', sa.String(255), nullable=False),
        sa.Column('value', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
    )

    # Unique constraint
    op.create_unique_constraint(
        'uq_datastore_org_scope_key',
        'workflow_datastores',
        ['organization_id', 'scope', 'scope_id', 'key']
    )

    # Indexes
    op.create_index(
        'ix_datastore_org_id',
        'workflow_datastores',
        ['organization_id']
    )

    op.create_index(
        'ix_datastore_lookup',
        'workflow_datastores',
        ['organization_id', 'scope', 'scope_id', 'key']
    )

    op.create_index(
        'ix_datastore_expires',
        'workflow_datastores',
        ['expires_at']
    )


def downgrade():
    op.drop_index('ix_datastore_expires', table_name='workflow_datastores')
    op.drop_index('ix_datastore_lookup', table_name='workflow_datastores')
    op.drop_index('ix_datastore_org_id', table_name='workflow_datastores')
    op.drop_constraint('uq_datastore_org_scope_key', 'workflow_datastores', type_='unique')
    op.drop_table('workflow_datastores')
