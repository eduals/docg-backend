"""Migrate clicksign nodes to signature nodes

Revision ID: o5p6q7r8s9t0
Revises: n4o5p6q7r8s9
Create Date: 2025-01-15
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'o5p6q7r8s9t0'
down_revision = 'n4o5p6q7r8s9'
branch_labels = None
depends_on = None


def upgrade():
    # Atualizar node_type de 'clicksign' para 'signature'
    # Adicionar provider='clicksign' no config se não existir
    op.execute("""
        UPDATE workflow_nodes
        SET node_type = 'signature',
            config = jsonb_set(
                COALESCE(config, '{}'::jsonb),
                '{provider}',
                '"clicksign"'
            )
        WHERE node_type = 'clicksign'
        AND (config->>'provider') IS NULL;
    """)
    
    # Para nodes que já têm provider no config, apenas atualizar node_type
    op.execute("""
        UPDATE workflow_nodes
        SET node_type = 'signature'
        WHERE node_type = 'clicksign'
        AND (config->>'provider') IS NOT NULL;
    """)


def downgrade():
    # Reverter: signature com provider=clicksign volta para clicksign
    op.execute("""
        UPDATE workflow_nodes
        SET node_type = 'clicksign',
            config = config - 'provider'
        WHERE node_type = 'signature'
        AND (config->>'provider') = 'clicksign';
    """)
