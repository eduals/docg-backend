"""Add hubspot_property_cache table

Revision ID: h8i9j0k1l2m3
Revises: g7h8i9j0k1l2
Create Date: 2025-12-05 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from datetime import datetime

# revision identifiers, used by Alembic.
revision = 'h8i9j0k1l2m3'
down_revision = 'g7h8i9j0k1l2'
branch_labels = None
depends_on = None


def upgrade():
    # Criar tabela hubspot_property_cache
    op.create_table(
        'hubspot_property_cache',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id'), nullable=False),
        sa.Column('object_type', sa.String(50), nullable=False),
        sa.Column('property_name', sa.String(255), nullable=False),
        sa.Column('label', sa.String(255)),
        sa.Column('type', sa.String(50)),
        sa.Column('options', postgresql.JSONB),
        sa.Column('cached_at', sa.DateTime, server_default=sa.func.now()),
    )
    
    # Índice único para organization_id + object_type + property_name
    op.create_unique_constraint(
        'unique_org_object_property', 
        'hubspot_property_cache', 
        ['organization_id', 'object_type', 'property_name']
    )
    
    # Índice para performance
    op.create_index(
        'idx_property_cache_org_object', 
        'hubspot_property_cache', 
        ['organization_id', 'object_type']
    )


def downgrade():
    # Remover índices
    op.drop_index('idx_property_cache_org_object', table_name='hubspot_property_cache')
    op.drop_constraint('unique_org_object_property', 'hubspot_property_cache', type_='unique')
    
    # Remover tabela
    op.drop_table('hubspot_property_cache')
