"""
Update Workflow Controller.
"""

from flask import request, jsonify, g
from app.database import db
from app.models import Workflow, WorkflowFieldMapping
from .helpers import workflow_to_dict, validate_post_actions


def update_workflow(workflow_id: str):
    """Atualiza um workflow"""
    workflow = Workflow.query.filter_by(
        id=workflow_id,
        organization_id=g.organization_id
    ).first_or_404()

    data = request.get_json()

    # Validar post_actions se fornecido
    if 'post_actions' in data:
        is_valid, error_msg = validate_post_actions(data['post_actions'])
        if not is_valid:
            return jsonify({'error': error_msg}), 400

    # Atualizar campos permitidos
    allowed_fields = [
        'name', 'description', 'source_connection_id', 'source_object_type',
        'source_config', 'template_id', 'output_folder_id', 'output_name_template',
        'create_pdf', 'trigger_type', 'trigger_config', 'post_actions', 'status'
    ]

    for field in allowed_fields:
        if field in data:
            setattr(workflow, field, data[field])

    # Atualizar field mappings se fornecidos
    if 'field_mappings' in data:
        # Remove mapeamentos existentes
        WorkflowFieldMapping.query.filter_by(workflow_id=workflow.id).delete()

        # Cria novos
        for mapping_data in data['field_mappings']:
            mapping = WorkflowFieldMapping(
                workflow_id=workflow.id,
                template_tag=mapping_data['template_tag'],
                source_field=mapping_data['source_field'],
                transform_type=mapping_data.get('transform_type'),
                transform_config=mapping_data.get('transform_config'),
                default_value=mapping_data.get('default_value')
            )
            db.session.add(mapping)

    db.session.commit()

    return jsonify({
        'success': True,
        'workflow': workflow_to_dict(workflow, include_mappings=True)
    })
