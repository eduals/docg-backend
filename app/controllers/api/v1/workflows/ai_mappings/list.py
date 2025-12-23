"""
List AI Mappings Controller.
"""

import uuid as uuid_module
from flask import jsonify, g
from app.models import Workflow, AIGenerationMapping


def list_ai_mappings(workflow_id: str):
    """Lista mapeamentos de IA de um workflow"""
    workflow_id_uuid = uuid_module.UUID(workflow_id) if isinstance(workflow_id, str) else workflow_id
    org_id = uuid_module.UUID(g.organization_id) if isinstance(g.organization_id, str) else g.organization_id

    workflow = Workflow.query.filter_by(
        id=workflow_id_uuid,
        organization_id=org_id
    ).first_or_404()

    mappings = AIGenerationMapping.query.filter_by(
        workflow_id=workflow.id
    ).order_by(AIGenerationMapping.created_at.desc()).all()

    return jsonify({
        'ai_mappings': [m.to_dict() for m in mappings]
    })
