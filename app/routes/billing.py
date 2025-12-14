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
