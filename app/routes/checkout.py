"""
Rotas para checkout do Stripe
"""
from flask import Blueprint, request, jsonify, g
from app.database import db
from app.models import Organization, User
from app.utils.auth import require_auth, require_org
from app.services.stripe_service import (
    get_plan_config,
    get_price_id,
    create_or_get_customer,
    create_checkout_session
)
import logging

logger = logging.getLogger(__name__)
checkout_bp = Blueprint('checkout', __name__, url_prefix='/api/v1/checkout')


@checkout_bp.route('/create-session', methods=['POST'])
@require_auth
@require_org
def create_session():
    """
    Cria uma sessão de checkout no Stripe
    
    Body:
    {
        "plan": "starter",  # starter, pro, team, enterprise
        "organization_id": "uuid"  # opcional, usa g.organization_id se não fornecido
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Body é obrigatório'}), 400
        
        plan_name = data.get('plan')
        if not plan_name:
            return jsonify({'error': 'plan é obrigatório'}), 400
        
        # Validar plano
        plan_config = get_plan_config(plan_name)
        if not plan_config:
            return jsonify({'error': f'Plano inválido: {plan_name}'}), 400
        
        price_id = get_price_id(plan_name)
        if not price_id or price_id == 'price_XXXXX':
            return jsonify({'error': f'Price ID não configurado para o plano {plan_name}'}), 400
        
        # Usar organization_id do contexto ou do body
        organization_id = data.get('organization_id') or g.organization_id
        if not organization_id:
            return jsonify({'error': 'organization_id é obrigatório'}), 400
        
        # Buscar organização
        org = Organization.query.filter_by(id=organization_id).first_or_404()
        
        # Verificar se usuário tem acesso à organização
        if str(org.id) != g.organization_id:
            return jsonify({'error': 'Acesso negado'}), 403
        
        # Buscar email do usuário atual
        user_email = request.headers.get('X-User-Email') or request.args.get('user_email')
        if not user_email:
            # Buscar primeiro admin da organização
            admin = User.query.filter_by(
                organization_id=org.id,
                role='admin'
            ).first()
            if admin:
                user_email = admin.email
            else:
                return jsonify({'error': 'Email do usuário não encontrado'}), 400
        
        # Criar ou buscar customer no Stripe
        customer_id = create_or_get_customer(
            organization=org,
            email=user_email,
            name=org.name
        )
        
        # Atualizar stripe_customer_id se necessário
        if org.stripe_customer_id != customer_id:
            org.stripe_customer_id = customer_id
            db.session.commit()
        
        # Verificar se está no onboarding
        is_onboarding = data.get('onboarding', False) or request.args.get('onboarding') == 'true'
        
        # Criar checkout session
        session = create_checkout_session(
            customer_id=customer_id,
            price_id=price_id,
            organization_id=org.id,
            plan_name=plan_name,
            is_onboarding=is_onboarding
        )
        
        logger.info(f'Checkout session criada: session_id={session.id}, organization_id={org.id}, plan={plan_name}')
        
        return jsonify({
            'success': True,
            'checkout_url': session.url,
            'session_id': session.id
        }), 200
        
    except Exception as e:
        logger.exception(f'Erro ao criar checkout session: {str(e)}')
        return jsonify({
            'error': 'Erro ao criar sessão de checkout',
            'message': str(e)
        }), 500
