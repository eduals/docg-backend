"""
Rotas para webhooks - endpoints públicos e de teste para webhook triggers.
"""
from flask import Blueprint, request, jsonify, g
from app.database import db
from app.models import Workflow, WorkflowNode, WorkflowExecution
from app.services.workflow_executor import WorkflowExecutor
from app.utils.auth import require_auth, require_org
import logging
import secrets
from datetime import datetime

logger = logging.getLogger(__name__)
webhooks_bp = Blueprint('webhooks', __name__, url_prefix='/api/v1/webhooks')


def _map_webhook_payload(payload, field_mapping):
    """
    Mapeia campos do payload do webhook para source_data conforme field_mapping.
    
    Args:
        payload: Dict com dados recebidos do webhook
        field_mapping: Dict com mapeamento {target_field: source_path}
    
    Returns:
        Dict com source_data mapeado
    """
    source_data = {}
    
    if not field_mapping:
        # Se não há mapeamento, usar payload completo
        return payload
    
    def get_nested_value(obj, path):
        """Obtém valor aninhado usando path como 'payload.deal.id'"""
        keys = path.split('.')
        value = obj
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None
            if value is None:
                return None
        return value
    
    for target_field, source_path in field_mapping.items():
        value = get_nested_value(payload, source_path)
        if value is not None:
            source_data[target_field] = value
    
    return source_data


@webhooks_bp.route('/<workflow_id>/<webhook_token>', methods=['POST', 'GET'])
def receive_webhook(workflow_id, webhook_token):
    """
    Endpoint público para receber webhooks.
    Não requer autenticação - usa webhook_token para validação.
    
    Args:
        workflow_id: UUID do workflow
        webhook_token: Token único do webhook trigger node
    """
    try:
        # Buscar trigger node pelo token
        trigger_node = WorkflowNode.query.filter_by(
            webhook_token=webhook_token,
            node_type='trigger',
            workflow_id=workflow_id
        ).first()
        
        if not trigger_node:
            logger.warning(f'Webhook token inválido: {webhook_token}')
            return jsonify({'error': 'Invalid webhook token'}), 401
        
        # Verificar se workflow está ativo
        workflow = Workflow.query.get(workflow_id)
        if not workflow or workflow.status != 'active':
            logger.warning(f'Workflow não encontrado ou inativo: {workflow_id}')
            return jsonify({'error': 'Workflow not found or inactive'}), 404
        
        # Extrair payload
        if request.is_json:
            payload = request.get_json()
        else:
            payload = request.form.to_dict() or {}
        
        # Obter field mapping do config
        config = trigger_node.config or {}
        field_mapping = config.get('field_mapping', {})
        source_object_type = config.get('source_object_type', 'webhook')
        
        # Mapear payload para source_data
        source_data = _map_webhook_payload(payload, field_mapping)
        
        # Determinar source_object_id (pode vir do payload ou gerar)
        source_object_id = source_data.get('id') or source_data.get('object_id') or f'webhook_{datetime.utcnow().isoformat()}'
        
        # Criar execução do workflow
        executor = WorkflowExecutor()
        
        # Executar workflow de forma assíncrona (ou síncrona por enquanto)
        # TODO: Considerar usar Celery para execução assíncrona
        try:
            execution = executor.execute_workflow(
                workflow=workflow,
                source_object_id=str(source_object_id),
                source_object_type=source_object_type,
                user_id=None
            )
            
            logger.info(f'Webhook executado com sucesso: workflow={workflow_id}, execution={execution.id}')
            
            return jsonify({
                'success': True,
                'execution_id': str(execution.id),
                'status': execution.status
            }), 200
            
        except Exception as e:
            logger.error(f'Erro ao executar workflow via webhook: {str(e)}')
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
        
    except Exception as e:
        logger.exception(f'Erro ao processar webhook: {str(e)}')
        return jsonify({'error': 'Internal server error'}), 500


@webhooks_bp.route('/test/<workflow_id>', methods=['POST'])
@require_auth
@require_org
def test_webhook(workflow_id):
    """
    Endpoint para testar webhook trigger.
    Requer autenticação.
    
    Envia um POST de teste para o webhook endpoint.
    """
    try:
        workflow = Workflow.query.filter_by(
            id=workflow_id,
            organization_id=g.organization_id
        ).first_or_404()
        
        # Buscar trigger node webhook
        trigger_node = WorkflowNode.query.filter_by(
            workflow_id=workflow.id,
            node_type='trigger'
        ).first()
        
        if not trigger_node:
            return jsonify({'error': 'Trigger node não encontrado'}), 404
        
        config = trigger_node.config or {}
        # Verificar se é webhook trigger de múltiplas formas
        is_webhook_trigger = (
            config.get('trigger_type') == 'webhook' or
            config.get('source_object_type') == 'webhook' or
            trigger_node.webhook_token is not None
        )
        
        if not is_webhook_trigger:
            return jsonify({'error': 'Este workflow não usa webhook trigger'}), 400
        
        if not trigger_node.webhook_token:
            return jsonify({'error': 'Webhook token não configurado'}), 400
        
        # Obter URL base da API
        from flask import current_app
        api_base_url = current_app.config.get('API_BASE_URL', request.url_root.rstrip('/'))
        
        webhook_url = f"{api_base_url}/api/v1/webhooks/{workflow_id}/{trigger_node.webhook_token}"
        
        # Criar payload de teste
        test_payload = request.get_json() or {
            'test': True,
            'timestamp': datetime.utcnow().isoformat(),
            'data': {
                'id': 'test-123',
                'name': 'Test Object'
            }
        }
        
        # Enviar request de teste
        import requests
        try:
            response = requests.post(
                webhook_url,
                json=test_payload,
                timeout=30
            )
            
            return jsonify({
                'success': True,
                'webhook_url': webhook_url,
                'test_payload': test_payload,
                'response_status': response.status_code,
                'response_body': response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
            }), 200
            
        except requests.exceptions.RequestException as e:
            return jsonify({
                'success': False,
                'error': f'Erro ao enviar teste: {str(e)}'
            }), 500
        
    except Exception as e:
        logger.exception(f'Erro ao testar webhook: {str(e)}')
        return jsonify({'error': str(e)}), 500


@webhooks_bp.route('/logs/<workflow_id>', methods=['GET'])
@require_auth
@require_org
def get_webhook_logs(workflow_id):
    """
    Lista últimos webhooks recebidos para um workflow.
    Requer autenticação.
    """
    try:
        workflow = Workflow.query.filter_by(
            id=workflow_id,
            organization_id=g.organization_id
        ).first_or_404()
        
        # Buscar últimas execuções via webhook
        limit = request.args.get('limit', 10, type=int)
        
        executions = WorkflowExecution.query.filter_by(
            workflow_id=workflow.id,
            trigger_type='webhook'
        ).order_by(WorkflowExecution.created_at.desc()).limit(limit).all()
        
        logs = []
        for execution in executions:
            logs.append({
                'execution_id': str(execution.id),
                'status': execution.status,
                'trigger_data': execution.trigger_data,
                'created_at': execution.created_at.isoformat() if execution.created_at else None,
                'error_message': execution.error_message
            })
        
        return jsonify({
            'logs': logs,
            'total': len(logs)
        }), 200
        
    except Exception as e:
        logger.exception(f'Erro ao buscar logs de webhook: {str(e)}')
        return jsonify({'error': str(e)}), 500


@webhooks_bp.route('/regenerate-token/<workflow_id>', methods=['POST'])
@require_auth
@require_org
def regenerate_webhook_token(workflow_id):
    """
    Regenera o webhook token de um workflow.
    Requer autenticação.
    """
    try:
        workflow = Workflow.query.filter_by(
            id=workflow_id,
            organization_id=g.organization_id
        ).first_or_404()
        
        # Buscar trigger node webhook
        trigger_node = WorkflowNode.query.filter_by(
            workflow_id=workflow.id,
            node_type='trigger'
        ).first()
        
        if not trigger_node:
            return jsonify({'error': 'Trigger node não encontrado'}), 404
        
        config = trigger_node.config or {}
        # Verificar se é webhook trigger de múltiplas formas
        is_webhook_trigger = (
            config.get('trigger_type') == 'webhook' or
            config.get('source_object_type') == 'webhook' or
            trigger_node.webhook_token is not None
        )
        
        if not is_webhook_trigger:
            return jsonify({'error': 'Este workflow não usa webhook trigger'}), 400
        
        # Gerar novo token
        new_token = trigger_node.generate_webhook_token()
        db.session.commit()
        
        # Obter URL base da API
        from flask import current_app
        api_base_url = current_app.config.get('API_BASE_URL', request.url_root.rstrip('/'))
        webhook_url = f"{api_base_url}/api/v1/webhooks/{workflow_id}/{new_token}"
        
        return jsonify({
            'success': True,
            'webhook_token': new_token,
            'webhook_url': webhook_url
        }), 200
        
    except Exception as e:
        logger.exception(f'Erro ao regenerar token: {str(e)}')
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

