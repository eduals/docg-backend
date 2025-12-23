"""
Current Organization Controllers.
"""

from flask import request, jsonify, g
from app.database import db
from app.models import Organization, Workflow
from app.services.stripe_service import get_subscription_info, PLAN_CONFIG
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def get_my_organization():
    """Retorna organização do usuário atual com limites, uso e informações da assinatura"""
    try:
        org = Organization.query.filter_by(id=g.organization_id).first_or_404()

        # Sincronizar contador de workflows
        real_workflows_count = Workflow.query.filter_by(organization_id=org.id).count()
        if org.workflows_used != real_workflows_count:
            org.workflows_used = real_workflows_count

        # Garantir que limites estejam definidos baseado no plano
        plan_config = PLAN_CONFIG.get(org.plan, {})
        if plan_config:
            if org.users_limit is None and 'users_limit' in plan_config:
                org.users_limit = plan_config.get('users_limit')
            if org.documents_limit is None and 'documents_limit' in plan_config:
                org.documents_limit = plan_config.get('documents_limit')
            if org.workflows_limit is None and 'workflows_limit' in plan_config:
                org.workflows_limit = plan_config.get('workflows_limit')

        db.session.commit()

        org_dict = org.to_dict(include_limits=True)

        # Buscar informações da assinatura do Stripe
        subscription_info = None
        if org.stripe_subscription_id:
            subscription_data = get_subscription_info(org.stripe_subscription_id)
            if subscription_data:
                subscription_info = {
                    'status': subscription_data['status'],
                    'current_period_end': (
                        datetime.fromtimestamp(subscription_data['current_period_end']).isoformat()
                        if subscription_data.get('current_period_end') else None
                    ),
                    'cancel_at_period_end': subscription_data.get('cancel_at_period_end', False),
                    'cancel_at': (
                        datetime.fromtimestamp(subscription_data['cancel_at']).isoformat()
                        if subscription_data.get('cancel_at') else None
                    ),
                    'trial_end': (
                        datetime.fromtimestamp(subscription_data['trial_end']).isoformat()
                        if subscription_data.get('trial_end') else None
                    ),
                }

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


def update_my_organization():
    """Atualiza dados da organização do usuário atual"""
    try:
        org = Organization.query.filter_by(id=g.organization_id).first_or_404()
        data = request.get_json()

        if not data:
            return jsonify({'error': 'Body é obrigatório'}), 400

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


def get_organization_status(organization_id: str):
    """Retorna status da organização"""
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
