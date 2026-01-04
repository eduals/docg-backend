"""create_refresh_token_table

Revision ID: 80d4e53df7b2
Revises: bbb222ccc333
Create Date: 2026-01-03 22:40:39.592029

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '80d4e53df7b2'
down_revision = 'bbb222ccc333'
branch_labels = None
depends_on = None


def upgrade():
    # Create refresh_token table
    op.create_table('refresh_token',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('token', sa.String(length=255), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('revoked', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.Column('revoked_reason', sa.String(length=255), nullable=True),
        sa.Column('ip_address', sa.String(length=50), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE')
    )

    # Create indexes
    op.create_index('idx_refresh_token_token', 'refresh_token', ['token'], unique=True)
    op.create_index('idx_refresh_token_user_id', 'refresh_token', ['user_id'], unique=False)
    op.create_index('idx_refresh_token_expires_at', 'refresh_token', ['expires_at'], unique=False)


def downgrade():
    # Drop indexes
    op.drop_index('idx_refresh_token_expires_at', table_name='refresh_token')
    op.drop_index('idx_refresh_token_user_id', table_name='refresh_token')
    op.drop_index('idx_refresh_token_token', table_name='refresh_token')

    # Drop table
    op.drop_table('refresh_token')
