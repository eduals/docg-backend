"""Add ActivePieces authentication fields to User model

Revision ID: aaa111bbb222
Revises: 0b1e1afe50f7
Create Date: 2026-01-03 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'aaa111bbb222'
down_revision = '0b1e1afe50f7'
branch_labels = None
depends_on = None


def upgrade():
    # Add new columns to users table
    with op.batch_alter_table('users', schema=None) as batch_op:
        # Name fields (split from single 'name' field)
        batch_op.add_column(sa.Column('first_name', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('last_name', sa.String(length=100), nullable=True))

        # Authentication fields
        batch_op.add_column(sa.Column('password_hash', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('verified', sa.Boolean(), nullable=False, server_default='false'))

        # Preference fields
        batch_op.add_column(sa.Column('track_events', sa.Boolean(), nullable=False, server_default='true'))
        batch_op.add_column(sa.Column('news_letter', sa.Boolean(), nullable=False, server_default='false'))


def downgrade():
    # Remove added columns
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('news_letter')
        batch_op.drop_column('track_events')
        batch_op.drop_column('verified')
        batch_op.drop_column('password_hash')
        batch_op.drop_column('last_name')
        batch_op.drop_column('first_name')
