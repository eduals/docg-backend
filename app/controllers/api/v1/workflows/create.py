"""
Create Workflow Controller.
"""

from flask import request, jsonify, g
from app.database import db
from app.models import Workflow, WorkflowNode, Organization
from .helpers import workflow_to_dict, validate_post_actions


def create_workflow():
    """
    Cria um novo workflow com trigger node automaticamente.

    Body:
    {
        "name": "Quote Generator",
        "description": "...",
        "source_connection_id": "uuid",
        "source_object_type": "deal",
        "trigger_type": "manual",
        "trigger_config": {},
        "post_actions": {}
    }
    """
    data = request.get_json()

    # Validações
    if not data.get('name'):
        return jsonify({'error': 'name é obrigatório'}), 400

    # Validar post_actions se fornecido
    post_actions = data.get('post_actions')
    if post_actions:
        is_valid, error_msg = validate_post_actions(post_actions)
        if not is_valid:
            return jsonify({'error': error_msg}), 400

    # Verificar limite de workflows
    org = Organization.query.filter_by(id=g.organization_id).first()
    if org and not org.can_create_workflow():
        limit = org.workflows_limit
        current_count = Workflow.query.filter_by(organization_id=org.id).count()
        return jsonify({
            'error': f'Limite de workflows atingido ({current_count}/{limit}). Faça upgrade do plano para criar mais workflows.'
        }), 403

    # Criar workflow
    workflow = Workflow(
        organization_id=g.organization_id,
        name=data['name'],
        description=data.get('description'),
        post_actions=data.get('post_actions'),
        status='draft',
        created_by=data.get('user_id')
    )

    db.session.add(workflow)
    db.session.flush()

    # Criar trigger node automaticamente
    trigger_node_type = 'hubspot'  # Default
    if data.get('trigger_type') == 'webhook':
        trigger_node_type = 'webhook'
    elif data.get('source_type') == 'google-forms':
        trigger_node_type = 'google-forms'

    trigger_config = {
        'source_connection_id': str(data.get('source_connection_id')) if data.get('source_connection_id') else None,
        'source_object_type': data.get('source_object_type'),
        'trigger_config': data.get('trigger_config', {}),
        'field_mapping': data.get('field_mapping', {})
    }

    trigger_node = WorkflowNode(
        workflow_id=workflow.id,
        node_type=trigger_node_type,
        position=1,
        parent_node_id=None,
        config=trigger_config,
        status='draft'
    )

    # Se for webhook trigger, gerar token
    if trigger_node_type == 'webhook':
        trigger_node.generate_webhook_token()

    db.session.add(trigger_node)

    # Incrementar contador de workflows
    if org:
        org.increment_workflow_count()

    db.session.commit()

    return jsonify({
        'success': True,
        'workflow': workflow_to_dict(workflow, include_mappings=False),
        'trigger_node': trigger_node.to_dict(include_config=True)
    }), 201
