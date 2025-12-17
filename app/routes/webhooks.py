"""
Rotas para webhooks - endpoints públicos e de teste para webhook triggers.
"""
from flask import Blueprint, request, jsonify, g
from app.database import db
from app.models import Workflow, WorkflowNode, WorkflowExecution, Organization
from app.services.workflow_executor import WorkflowExecutor
from app.utils.auth import require_auth, require_org
from app.config import Config
import logging
import secrets
import stripe
from datetime import datetime

# Configurar Stripe
stripe.api_key = Config.STRIPE_SECRET_KEY

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
        # Buscar trigger node pelo token (webhook trigger)
        trigger_node = WorkflowNode.query.filter(
            WorkflowNode.webhook_token == webhook_token,
            WorkflowNode.workflow_id == workflow_id,
            WorkflowNode.node_type.in_(['webhook', 'trigger'])  # webhook ou trigger (compatibilidade) - usar TRIGGER_NODE_TYPES se necessário
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
        trigger_node = WorkflowNode.query.filter(
            WorkflowNode.workflow_id == workflow.id,
            WorkflowNode.node_type.in_(['webhook', 'trigger'])  # webhook ou trigger (compatibilidade) - usar TRIGGER_NODE_TYPES se necessário
        ).first()
        
        if not trigger_node:
            return jsonify({'error': 'Trigger node não encontrado'}), 404
        
        config = trigger_node.config or {}
        # Verificar se é webhook trigger de múltiplas formas
        is_webhook_trigger = (
            trigger_node.node_type == 'webhook' or
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
        trigger_node = WorkflowNode.query.filter(
            WorkflowNode.workflow_id == workflow.id,
            WorkflowNode.node_type.in_(['webhook', 'trigger'])  # webhook ou trigger (compatibilidade) - usar TRIGGER_NODE_TYPES se necessário
        ).first()
        
        if not trigger_node:
            return jsonify({'error': 'Trigger node não encontrado'}), 404
        
        config = trigger_node.config or {}
        # Verificar se é webhook trigger de múltiplas formas
        is_webhook_trigger = (
            trigger_node.node_type == 'webhook' or
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


@webhooks_bp.route('/stripe', methods=['POST'])
def stripe_webhook():
    """
    Endpoint para receber webhooks do Stripe.
    Não requer autenticação - usa assinatura do Stripe para validação.
    """
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')
    
    if not sig_header:
        logger.warning('Webhook Stripe sem assinatura')
        return jsonify({'error': 'Missing signature'}), 400
    
    try:
        # Verificar assinatura do webhook
        event = stripe.Webhook.construct_event(
            payload, sig_header, Config.STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        logger.error(f'Erro ao parsear payload do Stripe: {str(e)}')
        return jsonify({'error': 'Invalid payload'}), 400
    except stripe.error.SignatureVerificationError as e:
        logger.error(f'Erro ao verificar assinatura do Stripe: {str(e)}')
        return jsonify({'error': 'Invalid signature'}), 400
    
    # Processar evento
    event_type = event['type']
    event_data = event['data']['object']
    
    logger.info(f'Webhook Stripe recebido: {event_type}')
    
    try:
        if event_type == 'checkout.session.completed':
            _handle_checkout_completed(event_data)
        elif event_type == 'customer.subscription.created':
            _handle_subscription_created(event_data)
        elif event_type == 'customer.subscription.updated':
            _handle_subscription_updated(event_data)
        elif event_type == 'customer.subscription.deleted':
            _handle_subscription_deleted(event_data)
        elif event_type == 'invoice.payment_succeeded':
            _handle_payment_succeeded(event_data)
        elif event_type == 'invoice.payment_failed':
            _handle_payment_failed(event_data)
        else:
            logger.info(f'Evento Stripe não processado: {event_type}')
        
        return jsonify({'received': True}), 200
        
    except Exception as e:
        logger.exception(f'Erro ao processar webhook Stripe: {str(e)}')
        return jsonify({'error': str(e)}), 500


def _handle_checkout_completed(session):
    """Processa checkout.session.completed"""
    metadata = session.get('metadata', {})
    organization_id = metadata.get('organization_id')
    plan_name = metadata.get('plan')
    is_onboarding = metadata.get('onboarding', 'false').lower() == 'true'
    
    if not organization_id or not plan_name:
        logger.warning(f'Checkout session sem metadata necessário: {session.get("id")}')
        return
    
    try:
        org = Organization.query.filter_by(id=organization_id).first()
        if not org:
            logger.error(f'Organização não encontrada: {organization_id}')
            return
        
        # Buscar subscription do checkout session
        subscription_id = session.get('subscription')
        if subscription_id:
            subscription = stripe.Subscription.retrieve(subscription_id)
            
            subscription_data = {
                'subscription_id': subscription.id,
                'current_period_end': subscription.current_period_end,
                'billing_cycle_anchor': subscription.billing_cycle_anchor,
                'status': subscription.status,
            }
            
            # Atualizar organização com dados do plano
            org.update_plan_from_stripe(plan_name, subscription_data)
            
            logger.info(f'Organização {organization_id} atualizada com plano {plan_name}')
        else:
            logger.warning(f'Checkout session sem subscription: {session.get("id")}')
            
    except Exception as e:
        logger.exception(f'Erro ao processar checkout completed: {str(e)}')
        raise


def _handle_subscription_created(subscription):
    """Processa customer.subscription.created"""
    # Similar ao checkout completed, mas pode ser chamado separadamente
    customer_id = subscription.get('customer')
    if customer_id:
        try:
            customer = stripe.Customer.retrieve(customer_id)
            organization_id = customer.metadata.get('organization_id')
            
            if organization_id:
                org = Organization.query.filter_by(id=organization_id).first()
                if org and org.stripe_customer_id == customer_id:
                    # Subscription já foi processada no checkout, apenas log
                    logger.info(f'Subscription criada para organização {organization_id}')
        except Exception as e:
            logger.exception(f'Erro ao processar subscription created: {str(e)}')


def _handle_subscription_updated(subscription):
    """Processa customer.subscription.updated"""
    customer_id = subscription.get('customer')
    if customer_id:
        try:
            customer = stripe.Customer.retrieve(customer_id)
            organization_id = customer.metadata.get('organization_id')
            
            if organization_id:
                org = Organization.query.filter_by(id=organization_id).first()
                if org and org.stripe_customer_id == customer_id:
                    # Atualizar subscription_id se mudou
                    if org.stripe_subscription_id != subscription.id:
                        org.stripe_subscription_id = subscription.id
                    
                    # Verificar se plano mudou (através do price_id)
                    items = subscription.get('items', {}).get('data', [])
                    if items:
                        price_id = items[0].get('price', {}).get('id')
                        # Buscar plano pelo price_id
                        from app.services.stripe_service import PLAN_CONFIG
                        plan_name = None
                        for plan, config in PLAN_CONFIG.items():
                            if config.get('price_id') == price_id:
                                plan_name = plan
                                break
                        
                        if plan_name and org.plan != plan_name:
                            subscription_data = {
                                'subscription_id': subscription.id,
                                'current_period_end': subscription.current_period_end,
                                'billing_cycle_anchor': subscription.billing_cycle_anchor,
                                'status': subscription.status,
                            }
                            org.update_plan_from_stripe(plan_name, subscription_data)
                            logger.info(f'Plano atualizado para {plan_name} na organização {organization_id}')
                    
                    db.session.commit()
        except Exception as e:
            logger.exception(f'Erro ao processar subscription updated: {str(e)}')
            db.session.rollback()


def _handle_subscription_deleted(subscription):
    """Processa customer.subscription.deleted"""
    customer_id = subscription.get('customer')
    if customer_id:
        try:
            customer = stripe.Customer.retrieve(customer_id)
            organization_id = customer.metadata.get('organization_id')
            
            if organization_id:
                org = Organization.query.filter_by(id=organization_id).first()
                if org and org.stripe_customer_id == customer_id:
                    # Rebaixar para free
                    org.plan = 'free'
                    org.stripe_subscription_id = None
                    org.users_limit = 1
                    org.documents_limit = 10
                    org.workflows_limit = 5
                    org.plan_expires_at = None
                    db.session.commit()
                    logger.info(f'Organização {organization_id} rebaixada para free')
        except Exception as e:
            logger.exception(f'Erro ao processar subscription deleted: {str(e)}')
            db.session.rollback()


def _handle_payment_succeeded(invoice):
    """Processa invoice.payment_succeeded"""
    subscription_id = invoice.get('subscription')
    if subscription_id:
        try:
            subscription = stripe.Subscription.retrieve(subscription_id)
            customer_id = subscription.get('customer')
            customer = stripe.Customer.retrieve(customer_id)
            organization_id = customer.metadata.get('organization_id')
            
            if organization_id:
                org = Organization.query.filter_by(id=organization_id).first()
                if org:
                    # Renovar assinatura - atualizar plan_expires_at
                    if subscription.current_period_end:
                        from datetime import datetime
                        org.plan_expires_at = datetime.fromtimestamp(subscription.current_period_end)
                        org.is_active = True
                        db.session.commit()
                        logger.info(f'Pagamento bem-sucedido para organização {organization_id}')
        except Exception as e:
            logger.exception(f'Erro ao processar payment succeeded: {str(e)}')
            db.session.rollback()


def _handle_payment_failed(invoice):
    """Processa invoice.payment_failed"""
    subscription_id = invoice.get('subscription')
    if subscription_id:
        try:
            subscription = stripe.Subscription.retrieve(subscription_id)
            customer_id = subscription.get('customer')
            customer = stripe.Customer.retrieve(customer_id)
            organization_id = customer.metadata.get('organization_id')
            
            if organization_id:
                org = Organization.query.filter_by(id=organization_id).first()
                if org:
                    # Marcar como inativo ou notificar
                    # Por enquanto apenas log, pode implementar notificação depois
                    logger.warning(f'Pagamento falhou para organização {organization_id}')
                    # TODO: Enviar notificação por email
        except Exception as e:
            logger.exception(f'Erro ao processar payment failed: {str(e)}')


@webhooks_bp.route('/signature/<provider>', methods=['POST'])
def handle_signature_webhook(provider):
    """
    Endpoint único para webhooks de assinatura.
    
    Providers suportados: clicksign, zapsign
    """
    from app.services.integrations.signature.factory import SignatureProviderFactory
    from app.services.integrations.signature.base import SignatureStatus
    from app.models import SignatureRequest, DataSourceConnection
    
    provider = provider.lower()
    
    if not SignatureProviderFactory.is_provider_supported(provider):
        return jsonify({'error': f'Provider {provider} não suportado'}), 400
    
    try:
        payload = request.get_json()
        if not payload:
            return jsonify({'error': 'Payload vazio'}), 400
        
        # Extrair envelope_id do payload baseado no provider
        if provider == 'clicksign':
            envelope_id = payload.get('event', {}).get('data', {}).get('id')
        elif provider == 'zapsign':
            envelope_id = payload.get('doc_id')
        else:
            return jsonify({'error': 'Provider não suportado'}), 400
        
        if not envelope_id:
            return jsonify({'error': 'envelope_id não encontrado no payload'}), 400
        
        # Buscar SignatureRequest
        signature_request = SignatureRequest.query.filter_by(
            external_id=envelope_id,
            provider=provider
        ).first()
        
        if not signature_request:
            logger.warning(f"SignatureRequest não encontrado para {provider} envelope {envelope_id}")
            return jsonify({'error': 'SignatureRequest não encontrado'}), 404
        
        # Buscar conexão para obter adapter
        connection = DataSourceConnection.query.filter_by(
            organization_id=signature_request.organization_id,
            source_type=provider,
            status='active'
        ).first()
        
        if not connection:
            logger.error(f"Conexão {provider} não encontrada para organização {signature_request.organization_id}")
            return jsonify({'error': 'Conexão não encontrada'}), 404
        
        # Obter adapter
        adapter = SignatureProviderFactory.get_adapter(
            provider=provider,
            connection_id=str(connection.id),
            organization_id=str(signature_request.organization_id)
        )
        
        # Verificar assinatura do webhook
        if not adapter.verify_webhook_signature(request):
            logger.warning(f"Assinatura de webhook inválida para {provider}")
            return jsonify({'error': 'Assinatura inválida'}), 401
        
        # Parse evento
        event = adapter.parse_webhook_event(payload)
        
        # Atualizar SignatureRequest
        signature_request.status = event['status'].value
        if event['status'] == SignatureStatus.SIGNED:
            signature_request.completed_at = event['timestamp']
        elif event['status'] == SignatureStatus.CANCELED:
            signature_request.completed_at = event['timestamp']
        
        signature_request.webhook_data = payload
        db.session.commit()
        
        logger.info(f"Webhook processado: {provider} - {event['event_type']} - {envelope_id}")
        
        return jsonify({'success': True, 'event': event})
        
    except Exception as e:
        logger.error(f"Erro ao processar webhook {provider}: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

