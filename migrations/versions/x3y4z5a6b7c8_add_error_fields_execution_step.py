"""Add error_human and error_tech to execution_steps

Revision ID: x3y4z5a6b7c8
Revises: w2x3y4z5a6b7
Create Date: 2025-12-23

Feature 7: Steps Persistidos + Snapshots
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'x3y4z5a6b7c8'
down_revision = 'w2x3y4z5a6b7'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'execution_steps',
        sa.Column('error_human', sa.Text(), nullable=True)
    )

    op.add_column(
        'execution_steps',
        sa.Column('error_tech', sa.Text(), nullable=True)
    )


def downgrade():
    op.drop_column('execution_steps', 'error_tech')
    op.drop_column('execution_steps', 'error_human')
