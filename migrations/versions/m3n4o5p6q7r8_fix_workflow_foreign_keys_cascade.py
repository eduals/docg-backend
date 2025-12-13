"""Fix workflow foreign keys cascade

Revision ID: m3n4o5p6q7r8
Revises: l2m3n4o5p6q7
Create Date: 2025-12-13 10:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'm3n4o5p6q7r8'
down_revision = 'l2m3n4o5p6q7'
branch_labels = None
depends_on = None


def upgrade():
    # Atualizar foreign key de workflow_executions.workflow_id para CASCADE
    # Usar batch_alter_table para garantir compatibilidade
    with op.batch_alter_table('workflow_executions', schema=None) as batch_op:
        batch_op.drop_constraint('workflow_executions_workflow_id_fkey', type_='foreignkey')
        batch_op.create_foreign_key(
            'workflow_executions_workflow_id_fkey',
            'workflows',
            ['workflow_id'],
            ['id'],
            ondelete='CASCADE'
        )
    
    # Atualizar foreign key de workflow_field_mappings.workflow_id para CASCADE
    with op.batch_alter_table('workflow_field_mappings', schema=None) as batch_op:
        batch_op.drop_constraint('workflow_field_mappings_workflow_id_fkey', type_='foreignkey')
        batch_op.create_foreign_key(
            'workflow_field_mappings_workflow_id_fkey',
            'workflows',
            ['workflow_id'],
            ['id'],
            ondelete='CASCADE'
        )
    
    # Atualizar foreign key de generated_documents.workflow_id para SET NULL
    with op.batch_alter_table('generated_documents', schema=None) as batch_op:
        batch_op.drop_constraint('generated_documents_workflow_id_fkey', type_='foreignkey')
        batch_op.create_foreign_key(
            'generated_documents_workflow_id_fkey',
            'workflows',
            ['workflow_id'],
            ['id'],
            ondelete='SET NULL'
        )


def downgrade():
    # Reverter foreign key de workflow_executions.workflow_id
    with op.batch_alter_table('workflow_executions', schema=None) as batch_op:
        batch_op.drop_constraint('workflow_executions_workflow_id_fkey', type_='foreignkey')
        batch_op.create_foreign_key(
            'workflow_executions_workflow_id_fkey',
            'workflows',
            ['workflow_id'],
            ['id']
        )
    
    # Reverter foreign key de workflow_field_mappings.workflow_id
    with op.batch_alter_table('workflow_field_mappings', schema=None) as batch_op:
        batch_op.drop_constraint('workflow_field_mappings_workflow_id_fkey', type_='foreignkey')
        batch_op.create_foreign_key(
            'workflow_field_mappings_workflow_id_fkey',
            'workflows',
            ['workflow_id'],
            ['id']
        )
    
    # Reverter foreign key de generated_documents.workflow_id
    with op.batch_alter_table('generated_documents', schema=None) as batch_op:
        batch_op.drop_constraint('generated_documents_workflow_id_fkey', type_='foreignkey')
        batch_op.create_foreign_key(
            'generated_documents_workflow_id_fkey',
            'workflows',
            ['workflow_id'],
            ['id']
        )

