"""add activepieces tables

Revision ID: z5a6b7c8d9e0
Revises: y4z5a6b7c8d9
Create Date: 2026-01-03 08:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'z5a6b7c8d9e0'
down_revision = 'y4z5a6b7c8d9'
branch_labels = None
depends_on = None


def upgrade():
    # Platform table
    op.create_table('platform',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('external_id', sa.String(length=255), nullable=True),
        sa.Column('branding_logo', sa.String(length=512), nullable=True),
        sa.Column('branding_primary_color', sa.String(length=7), nullable=True),
        sa.Column('branding_full_logo_url', sa.String(length=512), nullable=True),
        sa.Column('sso_enabled', sa.Boolean(), nullable=True),
        sa.Column('sso_provider', sa.String(length=50), nullable=True),
        sa.Column('sso_config', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('filter_pieces_enabled', sa.Boolean(), nullable=True),
        sa.Column('allowed_pieces', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('blocked_pieces', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('plan_type', sa.String(length=50), nullable=True),
        sa.Column('max_projects', sa.Integer(), nullable=True),
        sa.Column('max_flows', sa.Integer(), nullable=True),
        sa.Column('max_runs_per_month', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('external_id')
    )

    # Project table
    op.create_table('project',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('display_name', sa.String(length=255), nullable=False),
        sa.Column('external_id', sa.String(length=255), nullable=True),
        sa.Column('platform_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('is_private', sa.Boolean(), nullable=True),
        sa.Column('max_flows', sa.Integer(), nullable=True),
        sa.Column('max_runs_per_month', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['platform_id'], ['platform.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )

    # Folder table
    op.create_table('folder',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('display_name', sa.String(length=255), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['project.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # ProjectRole table
    op.create_table('project_role',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('type', sa.String(length=50), nullable=False),
        sa.Column('permissions', postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column('platform_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['platform_id'], ['platform.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_project_role_platform_id', 'project_role', ['platform_id'], unique=False)
    op.create_index('idx_project_role_type', 'project_role', ['type'], unique=False)

    # ProjectMember table
    op.create_table('project_member',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('project_role_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('platform_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['project.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_role_id'], ['project_role.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'project_id', 'platform_id', name='uk_project_member_user_project')
    )
    op.create_index('idx_project_member_user_id', 'project_member', ['user_id'], unique=False)
    op.create_index('idx_project_member_project_id', 'project_member', ['project_id'], unique=False)
    op.create_index('idx_project_member_role_id', 'project_member', ['project_role_id'], unique=False)

    # UserInvitation table
    op.create_table('user_invitation',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('type', sa.String(length=50), nullable=False),
        sa.Column('platform_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('platform_role', sa.String(length=50), nullable=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('project_role_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint(
            "(type = 'PLATFORM' AND platform_role IS NOT NULL AND project_id IS NULL AND project_role_id IS NULL) OR "
            "(type = 'PROJECT' AND platform_role IS NULL AND project_id IS NOT NULL AND project_role_id IS NOT NULL)",
            name='ck_user_invitation_type_fields'
        ),
        sa.ForeignKeyConstraint(['platform_id'], ['platform.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['project.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_role_id'], ['project_role.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email', 'platform_id', 'project_id', name='uk_user_invitation_email_platform_project')
    )
    op.create_index('idx_user_invitation_email', 'user_invitation', ['email'], unique=False)
    op.create_index('idx_user_invitation_status', 'user_invitation', ['status'], unique=False)
    op.create_index('idx_user_invitation_platform_id', 'user_invitation', ['platform_id'], unique=False)
    op.create_index('idx_user_invitation_project_id', 'user_invitation', ['project_id'], unique=False)

    # Flow table
    op.create_table('flow',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('display_name', sa.String(length=255), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('folder_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('published_version_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('schedule', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['project.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['folder_id'], ['folder.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_flow_project_id', 'flow', ['project_id'], unique=False)
    op.create_index('idx_flow_folder_id', 'flow', ['folder_id'], unique=False)
    op.create_index('idx_flow_status', 'flow', ['status'], unique=False)

    # FlowVersion table
    op.create_table('flow_version',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('flow_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('display_name', sa.String(length=255), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('state', sa.String(length=50), nullable=False),
        sa.Column('trigger', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('definition', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('is_valid', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['flow_id'], ['flow.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_flow_version_flow_id', 'flow_version', ['flow_id'], unique=False)
    op.create_index('idx_flow_version_state', 'flow_version', ['state'], unique=False)

    # Add foreign key for published_version_id in flow table
    op.create_foreign_key('fk_flow_published_version', 'flow', 'flow_version', ['published_version_id'], ['id'], ondelete='SET NULL')

    # FlowRun table
    op.create_table('flow_run',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('flow_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('flow_version_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('progress', sa.Integer(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('current_step', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('last_error_human', sa.Text(), nullable=True),
        sa.Column('last_error_tech', sa.Text(), nullable=True),
        sa.Column('trigger_output', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('steps_output', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('preflight_summary', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('delivery_state', sa.String(length=20), nullable=True),
        sa.Column('signature_state', sa.String(length=20), nullable=True),
        sa.Column('recommended_actions', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('phase_metrics', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('correlation_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('paused_at', sa.DateTime(), nullable=True),
        sa.Column('pause_reason', sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(['flow_id'], ['flow.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['flow_version_id'], ['flow_version.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['project_id'], ['project.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_flow_run_flow_id', 'flow_run', ['flow_id'], unique=False)
    op.create_index('idx_flow_run_project_id', 'flow_run', ['project_id'], unique=False)
    op.create_index('idx_flow_run_status', 'flow_run', ['status'], unique=False)
    op.create_index('idx_flow_run_created_at', 'flow_run', ['created_at'], unique=False)
    op.create_index('idx_flow_run_correlation_id', 'flow_run', ['correlation_id'], unique=False)

    # FlowRunLog table
    op.create_table('flow_run_log',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('flow_run_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('step_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('level', sa.String(length=20), nullable=False),
        sa.Column('domain', sa.String(length=50), nullable=False),
        sa.Column('message_human', sa.Text(), nullable=False),
        sa.Column('details_tech', sa.Text(), nullable=True),
        sa.Column('correlation_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['flow_run_id'], ['flow_run.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_flow_run_log_flow_run_id', 'flow_run_log', ['flow_run_id'], unique=False)
    op.create_index('idx_flow_run_log_level', 'flow_run_log', ['level'], unique=False)
    op.create_index('idx_flow_run_log_domain', 'flow_run_log', ['domain'], unique=False)
    op.create_index('idx_flow_run_log_timestamp', 'flow_run_log', ['timestamp'], unique=False)
    op.create_index('idx_flow_run_log_correlation_id', 'flow_run_log', ['correlation_id'], unique=False)

    # TriggerEvent table
    op.create_table('trigger_event',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('flow_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source_name', sa.String(length=100), nullable=False),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.ForeignKeyConstraint(['flow_id'], ['flow.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['project.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_trigger_event_flow_id', 'trigger_event', ['flow_id'], unique=False)
    op.create_index('idx_trigger_event_status', 'trigger_event', ['status'], unique=False)
    op.create_index('idx_trigger_event_created_at', 'trigger_event', ['created_at'], unique=False)

    # AppConnection table
    op.create_table('app_connection',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('external_id', sa.String(length=255), nullable=False),
        sa.Column('display_name', sa.String(length=255), nullable=False),
        sa.Column('piece_name', sa.String(length=100), nullable=False),
        sa.Column('piece_version', sa.String(length=50), nullable=False),
        sa.Column('type', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('value', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['project.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_app_connection_project_id', 'app_connection', ['project_id'], unique=False)
    op.create_index('idx_app_connection_piece_name', 'app_connection', ['piece_name'], unique=False)
    op.create_index('idx_app_connection_external_id', 'app_connection', ['external_id'], unique=False)

    # ConnectionKey table
    op.create_table('connection_key',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('piece_name', sa.String(length=100), nullable=False),
        sa.Column('client_id', sa.String(length=512), nullable=False),
        sa.Column('client_secret', sa.String(length=512), nullable=False),
        sa.Column('redirect_uri', sa.String(length=512), nullable=True),
        sa.Column('scopes', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('platform_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(['platform_id'], ['platform.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('piece_name')
    )

    # Add new columns to users table
    op.add_column('users', sa.Column('platform_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('users', sa.Column('platform_role', sa.String(length=50), nullable=True))
    op.add_column('users', sa.Column('status', sa.String(length=50), nullable=True))
    op.add_column('users', sa.Column('identity_id', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('external_id', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('last_active_date', sa.DateTime(), nullable=True))

    op.create_foreign_key('fk_user_platform', 'users', 'platform', ['platform_id'], ['id'], ondelete='SET NULL')
    op.create_unique_constraint('uk_user_identity_id', 'users', ['identity_id'])


def downgrade():
    # Remove foreign keys and columns from users table
    op.drop_constraint('uk_user_identity_id', 'users', type_='unique')
    op.drop_constraint('fk_user_platform', 'users', type_='foreignkey')
    op.drop_column('users', 'last_active_date')
    op.drop_column('users', 'external_id')
    op.drop_column('users', 'identity_id')
    op.drop_column('users', 'status')
    op.drop_column('users', 'platform_role')
    op.drop_column('users', 'platform_id')

    # Drop tables in reverse order (respecting foreign keys)
    op.drop_table('connection_key')
    op.drop_table('app_connection')
    op.drop_table('trigger_event')
    op.drop_table('flow_run_log')
    op.drop_table('flow_run')
    op.drop_table('flow_version')
    op.drop_table('flow')
    op.drop_table('user_invitation')
    op.drop_table('project_member')
    op.drop_table('project_role')
    op.drop_table('folder')
    op.drop_table('project')
    op.drop_table('platform')
