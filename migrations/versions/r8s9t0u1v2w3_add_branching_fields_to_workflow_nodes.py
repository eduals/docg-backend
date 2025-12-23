"""Add branching fields to workflow_nodes

Revision ID: r8s9t0u1v2w3
Revises: q7r8s9t0u1v2
Create Date: 2024-12-22

Adds support for workflow branching (conditional execution paths):
- structural_type: 'single' (default), 'branch', or 'paths'
- branch_conditions: JSONB with conditions for branching logic

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'r8s9t0u1v2w3'
down_revision = 'q7r8s9t0u1v2'
branch_labels = None
depends_on = None


def upgrade():
    # Add structural_type column
    op.add_column(
        'workflow_nodes',
        sa.Column(
            'structural_type',
            sa.String(20),
            nullable=False,
            server_default='single'
        )
    )

    # Add branch_conditions column (JSONB)
    op.add_column(
        'workflow_nodes',
        sa.Column(
            'branch_conditions',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True
        )
    )

    # Create index for structural_type (useful for queries filtering by type)
    op.create_index(
        'ix_workflow_nodes_structural_type',
        'workflow_nodes',
        ['structural_type']
    )


def downgrade():
    op.drop_index('ix_workflow_nodes_structural_type', table_name='workflow_nodes')
    op.drop_column('workflow_nodes', 'branch_conditions')
    op.drop_column('workflow_nodes', 'structural_type')
