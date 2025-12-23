"""
Get Workflow Field Mappings Controller.
"""

from flask import jsonify, g
from app.models import Workflow, WorkflowNode


def get_workflow_field_mappings(workflow_id: str):
    """
    Retorna field mappings de todos os nodes Google Docs do workflow.
    Útil para mostrar no HubSpot App quais tags serão preenchidas.
    """
    workflow = Workflow.query.filter_by(
        id=workflow_id,
        organization_id=g.organization_id
    ).first_or_404()

    # Buscar nodes Google Docs
    google_docs_nodes = WorkflowNode.query.filter_by(
        workflow_id=workflow.id,
        node_type='google-docs'
    ).all()

    # Extrair field mappings de cada node
    all_mappings = []
    for node in google_docs_nodes:
        config = node.config or {}
        field_mappings = config.get('field_mappings', [])
        for mapping in field_mappings:
            all_mappings.append({
                'node_id': str(node.id),
                'template_tag': mapping.get('template_tag'),
                'source_field': mapping.get('source_field'),
                'transform_type': mapping.get('transform_type'),
                'default_value': mapping.get('default_value')
            })

    # Também incluir field mappings legados do workflow
    legacy_mappings = list(workflow.field_mappings)
    for mapping in legacy_mappings:
        all_mappings.append({
            'node_id': None,
            'template_tag': mapping.template_tag,
            'source_field': mapping.source_field,
            'transform_type': mapping.transform_type,
            'default_value': mapping.default_value
        })

    # Buscar AI mappings também
    ai_mappings = []
    for mapping in workflow.ai_mappings:
        ai_mappings.append({
            'ai_tag': mapping.ai_tag,
            'source_fields': mapping.source_fields,
            'provider': mapping.provider,
            'model': mapping.model
        })

    return jsonify({
        'field_mappings': all_mappings,
        'ai_mappings': ai_mappings
    })
