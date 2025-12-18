"""Add storage fields to templates

Revision ID: p7q8r9s0t1u2
Revises: p6q7r8s9t0u1
Create Date: 2024-12-20 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'p7q8r9s0t1u2'
down_revision = 'p6q7r8s9t0u1'  # Verificar qual é a última migration antes de aplicar
branch_labels = None
depends_on = None


def upgrade():
    # Add storage fields to templates table
    op.add_column('templates', sa.Column('storage_type', sa.String(50), nullable=True))
    op.add_column('templates', sa.Column('storage_file_url', sa.String(500), nullable=True))
    op.add_column('templates', sa.Column('storage_file_key', sa.String(500), nullable=True))
    op.add_column('templates', sa.Column('file_size', sa.Integer(), nullable=True))
    op.add_column('templates', sa.Column('file_mime_type', sa.String(100), nullable=True))


def downgrade():
    # Remove storage fields from templates table
    op.drop_column('templates', 'file_mime_type')
    op.drop_column('templates', 'file_size')
    op.drop_column('templates', 'storage_file_key')
    op.drop_column('templates', 'storage_file_url')
    op.drop_column('templates', 'storage_type')
