"""
Preview Workflow Controller.
"""

import logging
from flask import request, jsonify, g
from app.models import Workflow, WorkflowNode, DataSourceConnection

logger = logging.getLogger(__name__)


def preview_workflow_data(workflow_id: str):
    """
    Preview dos dados que serão usados ao gerar documento.

    Query params:
    - object_type: deal, contact, company, ticket (obrigatório)
    - object_id: ID do objeto no HubSpot (obrigatório)
    """
    workflow = Workflow.query.filter_by(
        id=workflow_id,
        organization_id=g.organization_id
    ).first_or_404()

    object_type = request.args.get('object_type')
    object_id = request.args.get('object_id')

    if not object_type or not object_id:
        return jsonify({
            'error': 'object_type e object_id são obrigatórios'
        }), 400

    try:
        # Buscar trigger node para obter conexão
        trigger_node = WorkflowNode.query.filter_by(
            workflow_id=workflow.id,
            node_type='trigger'
        ).first()

        if not trigger_node or not trigger_node.config:
            return jsonify({
                'error': 'Trigger node não configurado'
            }), 400

        trigger_config = trigger_node.config
        source_connection_id = trigger_config.get('source_connection_id')

        if not source_connection_id:
            return jsonify({
                'error': 'Conexão de dados não configurada no trigger'
            }), 400

        # Buscar conexão
        connection = DataSourceConnection.query.get(source_connection_id)
        if not connection:
            return jsonify({
                'error': 'Conexão não encontrada'
            }), 400

        # Buscar dados do objeto
        from app.services.data_sources.hubspot import HubSpotDataSource
        data_source = HubSpotDataSource(connection)
        source_data = data_source.get_object_data(object_type, object_id)

        # Normalizar dados
        if isinstance(source_data, dict) and 'properties' in source_data:
            properties = source_data.pop('properties', {})
            if isinstance(properties, dict):
                source_data.update(properties)

        # Buscar field mappings
        google_docs_nodes = WorkflowNode.query.filter_by(
            workflow_id=workflow.id,
            node_type='google-docs'
        ).all()

        field_mappings_preview = []
        for node in google_docs_nodes:
            config = node.config or {}
            field_mappings = config.get('field_mappings', [])

            for mapping in field_mappings:
                template_tag = mapping.get('template_tag')
                source_field = mapping.get('source_field')

                # Buscar valor
                from app.services.document_generation.tag_processor import TagProcessor
                value = TagProcessor._get_nested_value(source_data, source_field)

                field_mappings_preview.append({
                    'template_tag': template_tag,
                    'source_field': source_field,
                    'value': value,
                    'status': 'ok' if value is not None else 'missing',
                    'label': template_tag.replace('_', ' ').title()
                })

        # Buscar AI mappings
        ai_mappings_preview = []
        for mapping in workflow.ai_mappings:
            ai_mappings_preview.append({
                'ai_tag': mapping.ai_tag,
                'source_fields': mapping.source_fields,
                'provider': mapping.provider,
                'model': mapping.model,
                'preview': f'[AI: {mapping.ai_tag}]'
            })

        # Validação
        missing_fields = [m['source_field'] for m in field_mappings_preview if m['status'] == 'missing']
        all_tags_available = len(missing_fields) == 0

        return jsonify({
            'field_mappings': field_mappings_preview,
            'ai_mappings': ai_mappings_preview,
            'validation': {
                'all_tags_available': all_tags_available,
                'missing_fields': missing_fields,
                'warnings': []
            }
        })

    except Exception as e:
        logger.error(f"Erro ao gerar preview: {str(e)}")
        return jsonify({
            'error': str(e)
        }), 500
