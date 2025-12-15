"""
Rotas para billing e gerenciamento de assinaturas
"""
from flask import Blueprint, request, jsonify, g
from app.database import db
from app.models import Organization, User
from app.utils.auth import require_auth, require_org
from app.services.stripe_service import (
    create_customer_portal_session,
    get_subscription_info
)
from app.config import Config
import logging
import stripe

logger = logging.getLogger(__name__)
billing_bp = Blueprint('billing', __name__, url_prefix='/api/v1/billing')


@billing_bp.route('/subscription', methods=['GET'])
@require_auth
@require_org
def get_subscription():
    """
    Retorna informações da assinatura do Stripe da organização atual
    """
    try:
        org = Organization.query.filter_by(id=g.organization_id).first_or_404()
        
        if not org.stripe_subscription_id:
            return jsonify({
                'subscription': None,
                'message': 'Nenhuma assinatura encontrada'
            }), 200
        
        subscription_info = get_subscription_info(org.stripe_subscription_id)
        
        if not subscription_info:
            return jsonify({
                'subscription': None,
                'message': 'Assinatura não encontrada no Stripe'
            }), 404
        
        return jsonify({
            'subscription': subscription_info
        }), 200
        
    except Exception as e:
        logger.exception(f'Erro ao buscar informações da assinatura: {str(e)}')
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500


@billing_bp.route('/create-portal-session', methods=['POST'])
@require_auth
@require_org
def create_portal_session():
    """
    Cria uma sessão do Customer Portal do Stripe para gerenciar assinatura
    """
    try:
        org = Organization.query.filter_by(id=g.organization_id).first_or_404()
        
        if not org.stripe_customer_id:
            return jsonify({
                'error': 'Organização não possui customer_id no Stripe'
            }), 400
        
        # URL para retornar após gerenciar assinatura
        return_url = f"{Config.FRONTEND_URL}/usage/billing"
        
        # Criar sessão do portal
        portal_session = create_customer_portal_session(
            customer_id=org.stripe_customer_id,
            return_url=return_url
        )
        
        logger.info(f'Portal session criada para organização {org.id}: {portal_session.id}')
        
        return jsonify({
            'portal_url': portal_session.url
        }), 200
        
    except Exception as e:
        logger.exception(f'Erro ao criar portal session: {str(e)}')
        return jsonify({
            'error': 'Erro ao criar sessão do portal',
            'message': str(e)
        }), 500


@billing_bp.route('/invoices', methods=['GET'])
@require_auth
@require_org
def list_invoices():
    """
    Lista invoices do Stripe para a organização atual
    Query params:
    - limit: número de invoices (padrão: 10, máximo: 100)
    - starting_after: cursor para paginação
    """
    try:
        org = Organization.query.filter_by(id=g.organization_id).first_or_404()
        
        if not org.stripe_customer_id:
            return jsonify({
                'invoices': [],
                'has_more': False
            }), 200
        
        # Parâmetros de query
        limit = min(int(request.args.get('limit', 10)), 100)
        starting_after = request.args.get('starting_after')
        
        # Buscar invoices do Stripe
        params = {
            'customer': org.stripe_customer_id,
            'limit': limit,
        }
        
        if starting_after:
            params['starting_after'] = starting_after
        
        invoices = stripe.Invoice.list(**params)
        
        # Formatar invoices
        formatted_invoices = []
        for invoice in invoices.data:
            # Determinar nome do plano a partir do price_id
            plan_name = 'free'
            subscription_id = getattr(invoice, 'subscription', None)
            
            if subscription_id:
                try:
                    subscription = stripe.Subscription.retrieve(subscription_id)
                    if subscription.items.data:
                        price_id = subscription.items.data[0].price.id
                        # Mapear price_id para nome do plano
                        from app.services.stripe_service import PLAN_CONFIG
                        for plan, config in PLAN_CONFIG.items():
                            if config.get('price_id') == price_id:
                                plan_name = plan
                                break
                except stripe.error.InvalidRequestError:
                    pass
                except Exception as e:
                    logger.warning(f'Erro ao buscar subscription {subscription_id}: {str(e)}')
            
            formatted_invoice = {
                'id': invoice.id,
                'amount_paid': invoice.amount_paid or 0,
                'currency': getattr(invoice, 'currency', 'usd'),
                'status': invoice.status,
                'created': invoice.created,
                'period_start': getattr(invoice, 'period_start', None),
                'period_end': getattr(invoice, 'period_end', None),
                'subscription': subscription_id,
                'hosted_invoice_url': getattr(invoice, 'hosted_invoice_url', None),
                'plan_name': plan_name,
            }
            formatted_invoices.append(formatted_invoice)
        
        return jsonify({
            'invoices': formatted_invoices,
            'has_more': invoices.has_more
        }), 200
        
    except Exception as e:
        logger.exception(f'Erro ao listar invoices: {str(e)}')
        return jsonify({
            'error': 'Erro ao listar invoices',
            'message': str(e)
        }), 500


@billing_bp.route('/prices', methods=['GET'])
@require_auth
@require_org
def list_prices():
    """
    Lista todos os preços disponíveis no Stripe para facilitar configuração
    Endpoint auxiliar para desenvolvimento/configuração
    """
    try:
        from app.services.stripe_service import PLAN_CONFIG
        
        prices_info = []
        for plan_name, config in PLAN_CONFIG.items():
            product_id = config.get('product_id')
            current_price_id = config.get('price_id')
            
            plan_info = {
                'plan': plan_name,
                'product_id': product_id,
                'current_price_id': current_price_id,
                'available_prices': []
            }
            
            if product_id:
                try:
                    # Buscar todos os preços do produto
                    prices = stripe.Price.list(product=product_id, active=True)
                    for price in prices.data:
                        plan_info['available_prices'].append({
                            'id': price.id,
                            'amount': price.unit_amount,
                            'currency': price.currency,
                            'interval': price.recurring.interval if price.recurring else 'one_time',
                            'is_current': price.id == current_price_id
                        })
                except Exception as e:
                    logger.warning(f'Erro ao buscar preços para {plan_name}: {str(e)}')
            
            prices_info.append(plan_info)
        
        return jsonify({
            'prices': prices_info
        }), 200
        
    except Exception as e:
        logger.exception(f'Erro ao listar preços: {str(e)}')
        return jsonify({
            'error': 'Erro ao listar preços',
            'message': str(e)
        }), 500
