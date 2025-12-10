"""
Rotas para Custom Workflow Actions do HubSpot.
Endpoint chamado quando uma ação de workflow é executada no HubSpot.
"""

from flask import Blueprint, request, jsonify
import logging
import time
from datetime import datetime

logger = logging.getLogger(__name__)

hubspot_workflow_bp = Blueprint('hubspot_workflow', __name__, url_prefix='/api/v1/hubspot/workflow-action')


@hubspot_workflow_bp.route('', methods=['POST'])
def execute_workflow_action():
    """
    Endpoint chamado pelo HubSpot quando uma workflow action é executada.
    
    Body (do HubSpot):
    {
        "callbackId": "abc123",
        "origin": {
            "portalId": 123456,
            "actionDefinitionId": "uuid",
            "actionDefinitionVersion": 1
        },
        "object": {
            "objectId": 456,
            "objectType": "DEAL"
        },
        "inputFields": {
            "workflow_id": "uuid-do-workflow-docugen",
            "include_line_items": true,
            "send_to_clicksign": false
        }
    }
    """
    start_time = time.time()
    data = request.get_json()
    
    logger.info(f'Workflow action recebida: {data}')
    
    # Extrair dados do HubSpot
    callback_id = data.get('callbackId')
    origin = data.get('origin', {})
    portal_id = origin.get('portalId')
    
    obj = data.get('object', {})
    hubspot_object_id = str(obj.get('objectId'))
    hubspot_object_type = obj.get('objectType', '').lower()
    
    input_fields = data.get('inputFields', {})
    workflow_id = input_fields.get('workflow_id')
    include_line_items = input_fields.get('include_line_items', False)
    send_to_clicksign = input_fields.get('send_to_clicksign', False)
    
    if not workflow_id:
        return jsonify({
            'outputFields': {
                'document_id': '',
                'document_url': '',
                'pdf_url': '',
                'status': 'error',
                'error_message': 'Workflow não selecionado'
            }
        })
    
    try:
        # Importar serviços necessários
        from app.models import Workflow, WorkflowNode, GeneratedDocument
        from app.services.workflow_executor import WorkflowExecutor
        
        # Buscar workflow no banco
        workflow = Workflow.query.get(workflow_id)
        
        if not workflow:
            logger.error(f'Workflow não encontrado: {workflow_id}')
            return jsonify({
                'outputFields': {
                    'document_id': '',
                    'document_url': '',
                    'pdf_url': '',
                    'status': 'error',
                    'error_message': f'Workflow não encontrado: {workflow_id}'
                }
            })
        
        # Verificar se workflow tem nodes configurados
        nodes_count = WorkflowNode.query.filter_by(workflow_id=workflow.id).count()
        
        if nodes_count > 0:
            # Usar WorkflowExecutor (nova estrutura com nodes)
            executor = WorkflowExecutor()
            execution = executor.execute_workflow(
                workflow=workflow,
                source_object_id=hubspot_object_id,
                source_object_type=hubspot_object_type
            )
            
            # Buscar documento gerado
            if execution.generated_document_id:
                doc = GeneratedDocument.query.get(execution.generated_document_id)
                result = {
                    'document_id': str(doc.id),
                    'document_url': doc.google_doc_url,
                    'pdf_url': doc.pdf_url,
                    'document_name': doc.name
                }
            else:
                raise Exception('Documento não foi gerado durante a execução')
        else:
            # Método legado (sem nodes) - manter compatibilidade
            from app.services.document_generation.generator import DocumentGenerator
            from app.routes.google_drive_routes import get_google_credentials
            from app.utils.helpers import get_organization_id_from_portal_id
            
            # Buscar organization_id do portal
            org_id = get_organization_id_from_portal_id(portal_id)
            if not org_id:
                raise Exception('Organização não encontrada para o portal')
            
            google_creds = get_google_credentials(org_id)
            if not google_creds:
                raise Exception('Credenciais do Google não configuradas')
            
            # Buscar dados do objeto
            from app.models import DataSourceConnection
            from app.services.data_sources.hubspot import HubSpotDataSource
            
            connection = workflow.source_connection
            if not connection:
                raise Exception('Conexão de dados não configurada no workflow')
            
            data_source = HubSpotDataSource(connection)
            source_data = data_source.get_object_data(
                hubspot_object_type,
                hubspot_object_id
            )
            
            generator = DocumentGenerator(google_creds)
            doc = generator.generate_from_workflow(
                workflow=workflow,
                source_data=source_data,
                source_object_id=hubspot_object_id,
                user_id=None,
                organization_id=org_id
            )
            
            result = {
                'document_id': str(doc.id),
                'document_url': doc.google_doc_url,
                'pdf_url': doc.pdf_url,
                'document_name': doc.name
            }
        
        execution_time = int((time.time() - start_time) * 1000)
        
        # Criar evento na timeline (opcional, se tiver token)
        try:
            from app.routes.hubspot_events import create_timeline_event_internal
            create_timeline_event_internal(
                object_type=hubspot_object_type,
                object_id=hubspot_object_id,
                event_type='document_generated',
                properties={
                    'document_name': result.get('document_name', 'Documento'),
                    'template_name': workflow.name,
                    'document_url': result.get('document_url', ''),
                    'workflow_name': workflow.name,
                    'format': result.get('format', 'docx')
                }
            )
        except Exception as e:
            logger.warning(f'Não foi possível criar evento na timeline: {str(e)}')
        
        # Enviar para ClickSign se solicitado
        if send_to_clicksign and result.get('document_id'):
            try:
                # TODO: Implementar integração com ClickSign
                logger.info(f'Enviando documento para ClickSign: {result.get("document_id")}')
            except Exception as e:
                logger.warning(f'Erro ao enviar para ClickSign: {str(e)}')
        
        logger.info(f'Documento gerado com sucesso em {execution_time}ms')
        
        return jsonify({
            'outputFields': {
                'document_id': str(result.get('document_id', '')),
                'document_url': result.get('document_url', ''),
                'pdf_url': result.get('pdf_url', ''),
                'status': 'success',
                'error_message': ''
            }
        })
        
    except Exception as e:
        logger.exception(f'Erro ao executar workflow action: {str(e)}')
        return jsonify({
            'outputFields': {
                'document_id': '',
                'document_url': '',
                'pdf_url': '',
                'status': 'error',
                'error_message': str(e)
            }
        })


@hubspot_workflow_bp.route('/workflows-options', methods=['GET'])
def get_workflows_options():
    """
    Retorna opções de workflows para o dropdown da workflow action.
    Chamado pelo HubSpot para popular o campo de seleção.
    """
    try:
        from app.models import Workflow
        
        # Buscar workflows ativos
        workflows = Workflow.query.filter_by(status='active').all()
        
        options = [
            {
                'label': workflow.name,
                'value': str(workflow.id),
                'description': workflow.description or ''
            }
            for workflow in workflows
        ]
        
        return jsonify({
            'options': options
        })
        
    except Exception as e:
        logger.exception(f'Erro ao buscar workflows: {str(e)}')
        return jsonify({
            'options': []
        })

