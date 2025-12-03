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
        from app.models import Workflow
        from app.services.document_generation.generator import DocumentGenerator
        
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
        
        # Gerar documento
        generator = DocumentGenerator()
        result = generator.generate_document(
            workflow_id=workflow.id,
            source_object_id=hubspot_object_id,
            source_object_type=hubspot_object_type,
            include_line_items=include_line_items
        )
        
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

