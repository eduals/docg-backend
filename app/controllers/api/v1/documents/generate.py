"""
Generate Document Controller.
"""

from flask import request, jsonify, g
from app.models import Workflow, GeneratedDocument
from app.services.document_generation import DocumentGenerator
from app.services.workflow_executor import WorkflowExecutor
from app.services.data_sources.hubspot import HubSpotDataSource
from app.routes.google_drive_routes import get_google_credentials
from .helpers import doc_to_dict
import logging
import uuid

logger = logging.getLogger(__name__)

def generate_document():
    """
    Gera um novo documento.

    Body:
    {
        "workflow_id": "uuid",
        "source_object_id": "123",
        "source_data": {...}
    }
    """
    data = request.get_json()

    workflow_id = data.get('workflow_id')
    source_object_id = data.get('source_object_id')
    source_data = data.get('source_data')

    if not workflow_id or not source_object_id:
        return jsonify({'error': 'workflow_id e source_object_id são obrigatórios'}), 400

    # Buscar workflow
    workflow = Workflow.query.filter_by(
        id=workflow_id,
        organization_id=g.organization_id
    ).first_or_404()

    # Se não passou source_data, busca da fonte
    if not source_data:
        connection = workflow.source_connection
        if not connection:
            return jsonify({'error': 'Conexão de dados não configurada'}), 400

        if connection.source_type == 'hubspot':
            additional_properties = []
            for mapping in workflow.field_mappings:
                source_field = mapping.source_field
                if source_field and '.' not in source_field:
                    additional_properties.append(source_field)

            data_source = HubSpotDataSource(connection)
            source_data = data_source.get_object_data(
                workflow.source_object_type,
                source_object_id,
                additional_properties=additional_properties if additional_properties else None
            )
        else:
            return jsonify({'error': f'Fonte {connection.source_type} não suportada ainda'}), 400

    try:
        nodes = WorkflowNode.query.filter_by(workflow_id=workflow.id).count()

        if nodes > 0:
            executor = WorkflowExecutor()
            execution = executor.execute_workflow(
                workflow=workflow,
                source_object_id=source_object_id,
                source_object_type=workflow.source_object_type or data.get('source_object_type'),
                user_id=data.get('user_id')
            )

            if execution.generated_document_id:
                doc = GeneratedDocument.query.get(execution.generated_document_id)
                return jsonify({
                    'success': True,
                    'document': doc_to_dict(doc),
                    'execution_id': str(execution.id)
                }), 201
            else:
                return jsonify({
                    'error': 'Documento não foi gerado durante a execução'
                }), 500
        else:
            organization_id = g.organization_id
            org_id_uuid = uuid.UUID(organization_id) if isinstance(organization_id, str) else organization_id

            google_creds = get_google_credentials(organization_id)
            if not google_creds:
                return jsonify({'error': 'Credenciais do Google não configuradas'}), 400

            generator = DocumentGenerator(google_creds)
            doc = generator.generate_from_workflow(
                workflow=workflow,
                source_data=source_data,
                source_object_id=source_object_id,
                user_id=data.get('user_id'),
                organization_id=org_id_uuid
            )

            return jsonify({
                'success': True,
                'document': doc_to_dict(doc)
            }), 201

    except Exception as e:
        logger.error(f"Erro ao gerar documento: {str(e)}")
        return jsonify({'error': str(e)}), 500
