"""Migrate GoogleOAuthToken and GoogleDriveConfig to use organization_id

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2025-11-21 22:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    # Migrar GoogleOAuthToken
    # 1. Adicionar coluna organization_id (temporária, nullable)
    op.add_column('google_oauth_tokens', sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=True))
    
    # 2. Migrar dados: buscar Organization via portal_id → DataSourceConnection
    # Isso será feito via script Python após a migration
    connection = op.get_bind()
    
    # Buscar todos os tokens
    tokens = connection.execute(sa.text("SELECT id, portal_id FROM google_oauth_tokens")).fetchall()
    
    for token_id, portal_id in tokens:
        if not portal_id:
            # Se portal_id for NULL, deletar o token (não há como associar)
            connection.execute(
                sa.text("DELETE FROM google_oauth_tokens WHERE id = :token_id"),
                {'token_id': token_id}
            )
            continue
            
        # Buscar organization_id via DataSourceConnection
        result = connection.execute(
            sa.text("""
                SELECT organization_id 
                FROM data_source_connections 
                WHERE source_type = 'hubspot' 
                AND (config->>'portal_id')::text = :portal_id
                LIMIT 1
            """),
            {'portal_id': str(portal_id)}
        ).fetchone()
        
        if result:
            org_id = result[0]
            # Atualizar token com organization_id
            connection.execute(
                sa.text("UPDATE google_oauth_tokens SET organization_id = :org_id WHERE id = :token_id"),
                {'org_id': org_id, 'token_id': token_id}
            )
        else:
            # Se não encontrar correspondência, deletar o token (órfão)
            connection.execute(
                sa.text("DELETE FROM google_oauth_tokens WHERE id = :token_id"),
                {'token_id': token_id}
            )
    
    # 3. Remover índice único de portal_id
    op.drop_index('ix_google_oauth_tokens_portal_id', table_name='google_oauth_tokens', if_exists=True)
    
    # 4. Remover coluna portal_id
    op.drop_column('google_oauth_tokens', 'portal_id')
    
    # 5. Tornar organization_id não-nullable e adicionar FK
    op.alter_column('google_oauth_tokens', 'organization_id', nullable=False)
    op.create_foreign_key('fk_google_oauth_tokens_organization', 'google_oauth_tokens', 'organizations', ['organization_id'], ['id'])
    op.create_index('ix_google_oauth_tokens_organization_id', 'google_oauth_tokens', ['organization_id'], unique=True)
    
    # Migrar GoogleDriveConfig
    # 1. Adicionar coluna organization_id (temporária, nullable)
    op.add_column('google_drive_config', sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=True))
    
    # 2. Migrar dados
    configs = connection.execute(sa.text("SELECT id, portal_id FROM google_drive_config")).fetchall()
    
    for config_id, portal_id in configs:
        if not portal_id:
            # Se portal_id for NULL, deletar o config (não há como associar)
            connection.execute(
                sa.text("DELETE FROM google_drive_config WHERE id = :config_id"),
                {'config_id': config_id}
            )
            continue
            
        # Buscar organization_id via DataSourceConnection
        result = connection.execute(
            sa.text("""
                SELECT organization_id 
                FROM data_source_connections 
                WHERE source_type = 'hubspot' 
                AND (config->>'portal_id')::text = :portal_id
                LIMIT 1
            """),
            {'portal_id': str(portal_id)}
        ).fetchone()
        
        if result:
            org_id = result[0]
            # Atualizar config com organization_id
            connection.execute(
                sa.text("UPDATE google_drive_config SET organization_id = :org_id WHERE id = :config_id"),
                {'org_id': org_id, 'config_id': config_id}
            )
        else:
            # Se não encontrar correspondência, deletar o config (órfão)
            connection.execute(
                sa.text("DELETE FROM google_drive_config WHERE id = :config_id"),
                {'config_id': config_id}
            )
    
    # 3. Remover índice único de portal_id
    op.drop_index('ix_google_drive_config_portal_id', table_name='google_drive_config', if_exists=True)
    
    # 4. Remover coluna portal_id
    op.drop_column('google_drive_config', 'portal_id')
    
    # 5. Tornar organization_id não-nullable e adicionar FK
    op.alter_column('google_drive_config', 'organization_id', nullable=False)
    op.create_foreign_key('fk_google_drive_config_organization', 'google_drive_config', 'organizations', ['organization_id'], ['id'])
    op.create_index('ix_google_drive_config_organization_id', 'google_drive_config', ['organization_id'], unique=True)


def downgrade():
    # Reverter GoogleDriveConfig
    op.drop_index('ix_google_drive_config_organization_id', table_name='google_drive_config', if_exists=True)
    op.drop_constraint('fk_google_drive_config_organization', 'google_drive_config', type_='foreignkey')
    op.add_column('google_drive_config', sa.Column('portal_id', sa.String(255), nullable=True))
    op.create_index('ix_google_drive_config_portal_id', 'google_drive_config', ['portal_id'], unique=True)
    op.drop_column('google_drive_config', 'organization_id')
    
    # Reverter GoogleOAuthToken
    op.drop_index('ix_google_oauth_tokens_organization_id', table_name='google_oauth_tokens', if_exists=True)
    op.drop_constraint('fk_google_oauth_tokens_organization', 'google_oauth_tokens', type_='foreignkey')
    op.add_column('google_oauth_tokens', sa.Column('portal_id', sa.String(255), nullable=True))
    op.create_index('ix_google_oauth_tokens_portal_id', 'google_oauth_tokens', ['portal_id'], unique=True)
    op.drop_column('google_oauth_tokens', 'organization_id')

