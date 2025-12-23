"""
Tags Preview Controller

Provides endpoint for previewing tag resolution before document generation.
"""

from flask import request, jsonify, g
from app.models import Workflow, DataSourceConnection
from app.tags.preview import TagPreviewService
from app.tags.context.builder import ContextBuilder
from app.services.data_sources.hubspot import HubSpotDataSource
import logging

logger = logging.getLogger(__name__)


def preview_tags(workflow_id: str):
    """
    Preview tag resolution for a workflow.

    POST /api/v1/workflows/{workflow_id}/tags/preview

    Request Body:
    {
        "object_type": "deal",          # Type of object (deal, contact, etc)
        "object_id": "123456",          # ID of the object in the source
        "template_content": "...",      # Optional: override template content
        "template_id": "uuid"           # Optional: specific template ID
    }

    Response:
    {
        "tags": [
            {"tag": "{{trigger.deal.amount}}", "resolved": 50000, "status": "ok"},
            {"tag": "{{trigger.deal.custom}}", "resolved": null, "status": "warning", "message": "..."}
        ],
        "loops": [...],
        "conditionals": [...],
        "warnings": [...],
        "errors": [...],
        "sample_output": "...",
        "stats": {
            "total_tags": 10,
            "resolved": 8,
            "warnings": 1,
            "errors": 1
        }
    }
    """
    # Get workflow
    workflow = Workflow.query.filter_by(
        id=workflow_id,
        organization_id=g.organization_id
    ).first()

    if not workflow:
        return jsonify({'error': 'Workflow not found'}), 404

    data = request.get_json() or {}
    object_type = data.get('object_type')
    object_id = data.get('object_id')
    template_content = data.get('template_content')
    template_id = data.get('template_id')

    if not object_type or not object_id:
        return jsonify({
            'error': 'object_type and object_id are required'
        }), 400

    try:
        # Determine source from workflow
        trigger_source = 'generic'
        connection_id = None

        if workflow.nodes:
            for node in workflow.nodes:
                if node.get('type') == 'trigger':
                    node_data = node.get('data', {})
                    app_key = node_data.get('app_key', '')
                    connection_id = node_data.get('connection_id')

                    if 'hubspot' in app_key.lower():
                        trigger_source = 'hubspot'
                    elif 'google_forms' in app_key.lower():
                        trigger_source = 'google_forms'
                    elif 'stripe' in app_key.lower():
                        trigger_source = 'stripe'
                    elif 'webhook' in app_key.lower():
                        trigger_source = 'webhook'
                    break

        # Fetch actual data from source
        trigger_data = {}

        if trigger_source == 'hubspot' and connection_id:
            trigger_data = _fetch_hubspot_data(
                connection_id,
                object_type,
                object_id,
                g.organization_id
            )
        else:
            # For webhook/generic, use provided data or mock
            trigger_data = data.get('trigger_data', {
                'id': object_id,
                'object_type': object_type
            })

        # Get template content
        if not template_content:
            template_content = _get_template_content(workflow, template_id)

        if not template_content:
            return jsonify({
                'error': 'No template content available. Provide template_content or ensure workflow has a template.'
            }), 400

        # Build workflow metadata
        workflow_metadata = {
            'id': str(workflow.id),
            'name': workflow.name
        }

        # Create preview service
        preview_service = TagPreviewService(locale='pt_BR')

        # Generate preview
        result = preview_service.preview_from_trigger(
            template_content=template_content,
            trigger_data=trigger_data,
            trigger_source=trigger_source,
            workflow_metadata=workflow_metadata,
            options={'max_sample_items': 5}
        )

        return jsonify(result.to_dict())

    except Exception as e:
        logger.exception(f"Error previewing tags for workflow {workflow_id}")
        return jsonify({
            'error': str(e),
            'tags': [],
            'warnings': [],
            'errors': [str(e)],
            'stats': {'errors': 1}
        }), 500


def validate_template_tags(workflow_id: str):
    """
    Validate tag syntax in a template without resolving.

    POST /api/v1/workflows/{workflow_id}/tags/validate

    Request Body:
    {
        "template_content": "..."   # Template text to validate
    }

    Response:
    {
        "valid": true,
        "errors": [],
        "tags": ["{{trigger.deal.name}}", "{{trigger.deal.amount}}"],
        "tag_count": 2
    }
    """
    data = request.get_json() or {}
    template_content = data.get('template_content')

    if not template_content:
        return jsonify({'error': 'template_content is required'}), 400

    preview_service = TagPreviewService()
    result = preview_service.validate_tags(template_content)

    return jsonify(result)


def _fetch_hubspot_data(
    connection_id: str,
    object_type: str,
    object_id: str,
    organization_id: str
) -> dict:
    """Fetch data from HubSpot for preview."""
    try:
        connection = DataSourceConnection.query.filter_by(
            id=connection_id,
            organization_id=organization_id
        ).first()

        if not connection:
            return {'id': object_id, 'object_type': object_type, '_error': 'Connection not found'}

        # Get decrypted credentials
        credentials = connection.get_decrypted_credentials()
        access_token = credentials.get('access_token')

        if not access_token:
            return {'id': object_id, 'object_type': object_type, '_error': 'No access token'}

        # Use HubSpot data source to fetch
        hubspot = HubSpotDataSource(access_token=access_token)
        data = hubspot.get_object_data(object_type, object_id)

        if data:
            # Add object type marker
            data['_object_type'] = object_type
            return data

        return {'id': object_id, 'object_type': object_type, '_error': 'Object not found'}

    except Exception as e:
        logger.warning(f"Error fetching HubSpot data: {e}")
        return {'id': object_id, 'object_type': object_type, '_error': str(e)}


def _get_template_content(workflow, template_id: str = None) -> str:
    """Get template content from workflow or specific template."""
    try:
        # Check workflow nodes for template
        if workflow.nodes:
            for node in workflow.nodes:
                node_data = node.get('data', {})
                app_key = node_data.get('app_key', '')

                # Look for document generation nodes
                if 'google_docs' in app_key.lower() or 'word' in app_key.lower():
                    # Get template from node config
                    template_config = node_data.get('template', {})
                    if template_config.get('content'):
                        return template_config['content']

                    # Try to get from template_id
                    tid = template_id or template_config.get('id')
                    if tid:
                        from app.models import Template
                        template = Template.query.get(tid)
                        if template and template.detected_tags:
                            # Return a sample template with detected tags
                            tags = template.detected_tags or []
                            return '\n'.join([f'{{{{{tag}}}}}' for tag in tags])

        return None
    except Exception as e:
        logger.warning(f"Error getting template content: {e}")
        return None
