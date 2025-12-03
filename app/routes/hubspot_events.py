"""
Rotas para criar eventos na timeline do HubSpot.
"""

from flask import Blueprint, request, jsonify
import requests
import logging
from functools import wraps

logger = logging.getLogger(__name__)

hubspot_events_bp = Blueprint('hubspot_events', __name__, url_prefix='/api/v1/hubspot-events')


def get_hubspot_token():
    """
    Obtém o token de acesso do HubSpot do contexto da requisição.
    """
    return request.headers.get('X-HubSpot-Access-Token')


@hubspot_events_bp.route('/create', methods=['POST'])
def create_timeline_event():
    """
    Cria um evento na timeline do HubSpot.
    
    Body:
    {
        "object_type": "deal",
        "object_id": "123456",
        "event_type": "document_generated",
        "properties": {
            "document_name": "Contrato ABC",
            "template_name": "Template Contrato",
            "document_url": "https://docs.google.com/...",
            "workflow_name": "Gerar Contrato"
        }
    }
    """
    data = request.get_json()
    
    object_type = data.get('object_type')
    object_id = data.get('object_id')
    event_type = data.get('event_type')
    properties = data.get('properties', {})
    
    if not all([object_type, object_id, event_type]):
        return jsonify({
            'error': 'object_type, object_id e event_type são obrigatórios'
        }), 400
    
    hubspot_token = get_hubspot_token()
    
    if not hubspot_token:
        logger.warning('Token do HubSpot não fornecido')
        return jsonify({'error': 'Token do HubSpot não fornecido'}), 401
    
    try:
        # Criar evento via HubSpot Timeline Events API
        response = requests.post(
            'https://api.hubapi.com/crm/v3/timeline/events',
            headers={
                'Authorization': f'Bearer {hubspot_token}',
                'Content-Type': 'application/json'
            },
            json={
                'eventTemplateId': event_type,
                'objectId': object_id,
                'tokens': properties
            }
        )
        
        if response.status_code in [200, 201]:
            logger.info(f'Evento criado com sucesso: {event_type} para {object_type}/{object_id}')
            return jsonify({
                'success': True,
                'data': response.json() if response.text else {}
            })
        else:
            logger.error(f'Erro ao criar evento: {response.status_code} - {response.text}')
            return jsonify({
                'error': 'Erro ao criar evento no HubSpot',
                'details': response.text
            }), response.status_code
            
    except Exception as e:
        logger.exception(f'Erro ao criar evento: {str(e)}')
        return jsonify({'error': 'Erro interno'}), 500


@hubspot_events_bp.route('/document-generated', methods=['POST'])
def create_document_generated_event():
    """
    Cria um evento de documento gerado na timeline.
    
    Body:
    {
        "object_type": "deal",
        "object_id": "123456",
        "document_name": "Contrato ABC",
        "template_name": "Template Contrato",
        "document_url": "https://docs.google.com/...",
        "workflow_name": "Gerar Contrato",
        "format": "pdf"
    }
    """
    data = request.get_json()
    
    return create_timeline_event_internal(
        object_type=data.get('object_type'),
        object_id=data.get('object_id'),
        event_type='document_generated',
        properties={
            'document_name': data.get('document_name'),
            'template_name': data.get('template_name'),
            'document_url': data.get('document_url'),
            'workflow_name': data.get('workflow_name'),
            'format': data.get('format', 'docx')
        }
    )


@hubspot_events_bp.route('/document-signed', methods=['POST'])
def create_document_signed_event():
    """
    Cria um evento de documento assinado na timeline.
    
    Body:
    {
        "object_type": "deal",
        "object_id": "123456",
        "document_name": "Contrato ABC",
        "signature_status": "signed",
        "signed_by": "João Silva",
        "signed_at": "2025-12-03T10:00:00Z"
    }
    """
    data = request.get_json()
    
    return create_timeline_event_internal(
        object_type=data.get('object_type'),
        object_id=data.get('object_id'),
        event_type='document_signed',
        properties={
            'document_name': data.get('document_name'),
            'signature_status': data.get('signature_status'),
            'signed_by': data.get('signed_by'),
            'signed_at': data.get('signed_at')
        }
    )


@hubspot_events_bp.route('/workflow-executed', methods=['POST'])
def create_workflow_executed_event():
    """
    Cria um evento de workflow executado na timeline.
    
    Body:
    {
        "object_type": "deal",
        "object_id": "123456",
        "workflow_name": "Gerar Contrato",
        "execution_status": "success",
        "execution_time_ms": 1500,
        "documents_generated": 1
    }
    """
    data = request.get_json()
    
    return create_timeline_event_internal(
        object_type=data.get('object_type'),
        object_id=data.get('object_id'),
        event_type='workflow_executed',
        properties={
            'workflow_name': data.get('workflow_name'),
            'execution_status': data.get('execution_status'),
            'execution_time_ms': data.get('execution_time_ms'),
            'documents_generated': data.get('documents_generated')
        }
    )


def create_timeline_event_internal(object_type, object_id, event_type, properties):
    """
    Função interna para criar evento na timeline.
    """
    hubspot_token = get_hubspot_token()
    
    if not hubspot_token:
        # Se não tiver token, apenas logamos (para desenvolvimento)
        logger.info(f'Evento simulado: {event_type} para {object_type}/{object_id}')
        return jsonify({
            'success': True,
            'simulated': True,
            'message': 'Evento simulado (token não fornecido)'
        })
    
    try:
        response = requests.post(
            'https://api.hubapi.com/crm/v3/timeline/events',
            headers={
                'Authorization': f'Bearer {hubspot_token}',
                'Content-Type': 'application/json'
            },
            json={
                'eventTemplateId': event_type,
                'objectId': object_id,
                'tokens': properties
            }
        )
        
        if response.status_code in [200, 201]:
            return jsonify({
                'success': True,
                'data': response.json() if response.text else {}
            })
        else:
            return jsonify({
                'error': 'Erro ao criar evento',
                'details': response.text
            }), response.status_code
            
    except Exception as e:
        logger.exception(f'Erro ao criar evento: {str(e)}')
        return jsonify({'error': 'Erro interno'}), 500

