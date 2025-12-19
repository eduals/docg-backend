"""Add Temporal workflow fields

Revision ID: p6q7r8s9t0u1
Revises: 648d6d69e67d
Create Date: 2025-12-17 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'p6q7r8s9t0u1'
down_revision = '648d6d69e67d'
branch_labels = None
depends_on = None


def upgrade():
    # === WorkflowExecution ===
    # temporal_workflow_id: ID do workflow no Temporal
    op.add_column('workflow_executions', 
        sa.Column('temporal_workflow_id', sa.String(255), unique=True, nullable=True)
    )
    # temporal_run_id: Run ID do Temporal (para debug)
    op.add_column('workflow_executions', 
        sa.Column('temporal_run_id', sa.String(255), nullable=True)
    )
    # current_node_id: Node atual sendo executado
    op.add_column('workflow_executions', 
        sa.Column('current_node_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('workflow_nodes.id', ondelete='SET NULL'), nullable=True)
    )
    # execution_context: Snapshot do ExecutionContext (para retomada)
    op.add_column('workflow_executions', 
        sa.Column('execution_context', postgresql.JSONB(), nullable=True)
    )
    # execution_logs: Logs por node
    op.add_column('workflow_executions', 
        sa.Column('execution_logs', postgresql.JSONB(), server_default='[]', nullable=True)
    )
    
    # Índices para WorkflowExecution
    op.create_index('idx_execution_temporal_workflow_id', 'workflow_executions', ['temporal_workflow_id'], unique=True)
    op.create_index('idx_execution_status_workflow', 'workflow_executions', ['workflow_id', 'status'])
    
    # === SignatureRequest ===
    # node_id: Qual node criou esta request
    op.add_column('signature_requests', 
        sa.Column('node_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('workflow_nodes.id', ondelete='SET NULL'), nullable=True)
    )
    # workflow_execution_id: Qual execução criou esta request
    op.add_column('signature_requests', 
        sa.Column('workflow_execution_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('workflow_executions.id', ondelete='SET NULL'), nullable=True)
    )
    # signers_status: Status por signatário {"email": "signed|pending|declined"}
    op.add_column('signature_requests', 
        sa.Column('signers_status', postgresql.JSONB(), server_default='{}', nullable=True)
    )
    
    # Índice para SignatureRequest
    op.create_index('idx_signature_request_execution', 'signature_requests', ['workflow_execution_id'])


def downgrade():
    # SignatureRequest
    op.drop_index('idx_signature_request_execution', table_name='signature_requests')
    op.drop_column('signature_requests', 'signers_status')
    op.drop_column('signature_requests', 'workflow_execution_id')
    op.drop_column('signature_requests', 'node_id')
    
    # WorkflowExecution
    op.drop_index('idx_execution_status_workflow', table_name='workflow_executions')
    op.drop_index('idx_execution_temporal_workflow_id', table_name='workflow_executions')
    op.drop_column('workflow_executions', 'execution_logs')
    op.drop_column('workflow_executions', 'execution_context')
    op.drop_column('workflow_executions', 'current_node_id')
    op.drop_column('workflow_executions', 'temporal_run_id')
    op.drop_column('workflow_executions', 'temporal_workflow_id')


