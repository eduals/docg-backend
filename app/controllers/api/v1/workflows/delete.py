"""
Delete Workflow Controller.
"""

import logging
from flask import jsonify, g
from app.database import db
from app.models import Workflow, WorkflowFieldMapping, AIGenerationMapping, WorkflowNode, WorkflowExecution

logger = logging.getLogger(__name__)


def delete_workflow(workflow_id: str):
    """Deleta um workflow"""
    workflow = Workflow.query.filter_by(
        id=workflow_id,
        organization_id=g.organization_id
    ).first_or_404()

    # Deletar execuções explicitamente
    WorkflowExecution.query.filter_by(workflow_id=workflow.id).delete()

    # Deletar field mappings explicitamente
    WorkflowFieldMapping.query.filter_by(workflow_id=workflow.id).delete()

    # Deletar AI mappings explicitamente
    AIGenerationMapping.query.filter_by(workflow_id=workflow.id).delete()

    # Deletar nodes explicitamente
    WorkflowNode.query.filter_by(workflow_id=workflow.id).delete()

    # Deletar o workflow
    db.session.delete(workflow)
    db.session.commit()

    logger.info(f'Workflow {workflow_id} deletado com sucesso')

    return jsonify({'success': True})
