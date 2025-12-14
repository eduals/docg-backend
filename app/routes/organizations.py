from flask import Blueprint, request, jsonify, g
from app.database import db
from app.models import Organization
from app.utils.auth import require_auth, require_org, require_admin
from app.config import Config
from app.services.stripe_service import get_subscription_info
from datetime import datetime
import logging
import re
import uuid

logger = logging.getLogger(__name__)
organizations_bp = Blueprint('organizations', __name__, url_prefix='/api/v1/organizations')


@organizations_bp.route('', methods=['POST'])
@require_auth
def create_organization():
    """
    Cria uma nova organização (conta).
    Este é o primeiro passo do fluxo de criação de conta.
    
    Body:
    {
        "name": "Minha Empresa",
        "billing_email": "billing@empresa.com"
    }
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Body é obrigatório'}), 400
    
    required = ['name']
    for field in required:
        if not data.get(field):
            return jsonify({'error': f'{field} é obrigatório'}), 400
    
    # Gerar slug único baseado no nome
    slug_base = re.sub(r'[^a-z0-9]+', '-', data['name'].lower()).strip('-')
    slug = slug_base
    counter = 1
    
    # Garantir que slug é único
    while Organization.query.filter_by(slug=slug).first():
        slug = f"{slug_base}-{counter}"
        counter += 1
    
    # Criar organização
    plan_name = data.get('plan', 'free')
    org = Organization(
        name=data['name'],
        slug=slug,
        plan=plan_name,
        billing_email=data.get('billing_email')
    )
    
    # Aplicar limites do plano
    from app.services.stripe_service import PLAN_CONFIG
    plan_config = PLAN_CONFIG.get(plan_name, {})
    if plan_config:
        org.users_limit = plan_config.get('users_limit', org.users_limit)
        org.documents_limit = plan_config.get('documents_limit', org.documents_limit)
        org.workflows_limit = plan_config.get('workflows_limit', org.workflows_limit)
    
    db.session.add(org)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'organization': org.to_dict()
    }), 201


@organizations_bp.route('/<organization_id>', methods=['GET'])
@require_auth
@require_org
def get_organization(organization_id):
    """Retorna detalhes de uma organização"""
    # Verificar se usuário tem acesso
    if organization_id != g.organization_id:
        return jsonify({'error': 'Acesso negado'}), 403
    
    org = Organization.query.filter_by(id=organization_id).first_or_404()
    return jsonify(org.to_dict())


@organizations_bp.route('/<organization_id>', methods=['PUT'])
@require_auth
@require_org
@require_admin
def update_organization(organization_id):
    """Atualiza uma organização"""
    if organization_id != g.organization_id:
        return jsonify({'error': 'Acesso negado'}), 403
    
    org = Organization.query.filter_by(id=organization_id).first_or_404()
    data = request.get_json()
    
    # Atualizar campos permitidos
    allowed_fields = ['name', 'billing_email']
    
    for field in allowed_fields:
        if field in data:
            setattr(org, field, data[field])
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'organization': org.to_dict()
    })


@organizations_bp.route('/me', methods=['GET'])
@require_auth
@require_org
def get_my_organization():
    """Retorna organização do usuário atual com limites, uso e informações da assinatura"""
    try:
        org = Organization.query.filter_by(id=g.organization_id).first_or_404()
        
        # Sincronizar contador de workflows com contagem real (para manter consistência)
        from app.models import Workflow
        real_workflows_count = Workflow.query.filter_by(organization_id=org.id).count()
        if org.workflows_used != real_workflows_count:
            org.workflows_used = real_workflows_count
        
        # Garantir que limites estejam definidos baseado no plano
        from app.services.stripe_service import PLAN_CONFIG
        plan_config = PLAN_CONFIG.get(org.plan, {})
        if plan_config:
            # Aplicar limites se não estiverem definidos ou se forem None
            if org.users_limit is None and 'users_limit' in plan_config:
                org.users_limit = plan_config.get('users_limit')
            if org.documents_limit is None and 'documents_limit' in plan_config:
                org.documents_limit = plan_config.get('documents_limit')
            if org.workflows_limit is None and 'workflows_limit' in plan_config:
                org.workflows_limit = plan_config.get('workflows_limit')
        
        db.session.commit()
        
        org_dict = org.to_dict(include_limits=True)
        
        # Buscar informações da assinatura do Stripe se houver
        subscription_info = None
        if org.stripe_subscription_id:
            subscription_data = get_subscription_info(org.stripe_subscription_id)
            if subscription_data:
                # Formatar informações da assinatura
                from datetime import datetime
                subscription_info = {
                    'status': subscription_data['status'],
                    'current_period_end': datetime.fromtimestamp(subscription_data['current_period_end']).isoformat() if subscription_data.get('current_period_end') else None,
                    'cancel_at_period_end': subscription_data.get('cancel_at_period_end', False),
                    'cancel_at': datetime.fromtimestamp(subscription_data['cancel_at']).isoformat() if subscription_data.get('cancel_at') else None,
                    'trial_end': datetime.fromtimestamp(subscription_data['trial_end']).isoformat() if subscription_data.get('trial_end') else None,
                }
                
                # Adicionar informações do preço se disponível
                if subscription_data.get('price'):
                    price = subscription_data['price']
                    subscription_info['amount'] = price.get('unit_amount', 0)
                    subscription_info['currency'] = price.get('currency', 'brl')
                    subscription_info['interval'] = price.get('interval', 'month')
        
        org_dict['subscription_info'] = subscription_info
        
        return jsonify(org_dict), 200
    except Exception as e:
        logger.exception(f'Erro ao buscar organização: {str(e)}')
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500


@organizations_bp.route('/me', methods=['PUT'])
@require_auth
@require_org
@require_admin
def update_my_organization():
    """Atualiza dados da organização do usuário atual"""
    try:
        org = Organization.query.filter_by(id=g.organization_id).first_or_404()
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Body é obrigatório'}), 400
        
        # Atualizar campos permitidos
        allowed_fields = ['name', 'billing_email', 'onboarding_data']
        
        for field in allowed_fields:
            if field in data:
                setattr(org, field, data[field])
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'organization': org.to_dict(include_limits=True)
        }), 200
        
    except Exception as e:
        logger.exception(f'Erro ao atualizar organização: {str(e)}')
        db.session.rollback()
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500


@organizations_bp.route('/me/complete-onboarding', methods=['POST'])
@require_auth
@require_org
@require_admin
def complete_onboarding():
    """Marca onboarding como completo"""
    try:
        org = Organization.query.filter_by(id=g.organization_id).first_or_404()
        org.onboarding_completed = True
        db.session.commit()
        
        return jsonify({
            'success': True,
            'organization': org.to_dict(include_limits=True)
        }), 200
        
    except Exception as e:
        logger.exception(f'Erro ao completar onboarding: {str(e)}')
        db.session.rollback()
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500


@organizations_bp.route('/<organization_id>/status', methods=['GET'])
@require_auth
@require_org
def get_organization_status(organization_id):
    """Retorna status da organização (trial ativo, expirado, plano ativo)"""
    try:
        if organization_id != g.organization_id:
            return jsonify({'error': 'Acesso negado'}), 403
        
        org = Organization.query.filter_by(id=organization_id).first_or_404()
        status = org.get_status()
        
        return jsonify({
            'success': True,
            'data': {
                'status': status,
                'trial_expires_at': org.trial_expires_at.isoformat() if org.trial_expires_at else None,
                'plan_expires_at': org.plan_expires_at.isoformat() if org.plan_expires_at else None,
                'is_active': org.is_active
            }
        }), 200
        
    except Exception as e:
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500



