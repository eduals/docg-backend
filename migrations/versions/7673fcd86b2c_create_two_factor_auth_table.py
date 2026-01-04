"""create_two_factor_auth_table

Revision ID: 7673fcd86b2c
Revises: 80d4e53df7b2
Create Date: 2026-01-03 22:44:14.336716

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '7673fcd86b2c'
down_revision = '80d4e53df7b2'
branch_labels = None
depends_on = None


def upgrade():
    # Create two_factor_auth table
    op.create_table('two_factor_auth',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('secret', sa.String(length=32), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('verified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('backup_codes', sa.Text(), nullable=True),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('user_id')
    )

    # Create index
    op.create_index('idx_2fa_user_id', 'two_factor_auth', ['user_id'], unique=False)


def downgrade():
    # Drop index
    op.drop_index('idx_2fa_user_id', table_name='two_factor_auth')

    # Drop table
    op.drop_table('two_factor_auth')
