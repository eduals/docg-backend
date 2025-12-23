"""
Delete AI Mapping Controller.
"""

from flask import jsonify, g
from app.database import db
from app.models import Workflow, AIGenerationMapping


def delete_ai_mapping(workflow_id: str, mapping_id: str):
    """Deleta um mapeamento de IA"""
    workflow = Workflow.query.filter_by(
        id=workflow_id,
        organization_id=g.organization_id
    ).first_or_404()

    mapping = AIGenerationMapping.query.filter_by(
        id=mapping_id,
        workflow_id=workflow.id
    ).first_or_404()

    db.session.delete(mapping)
    db.session.commit()

    return jsonify({'success': True})
