from flask import Blueprint, request, jsonify, g
from app.database import db
from app.models import Organization
from app.utils.auth import require_auth, require_org, require_admin
from app.config import Config
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
    org = Organization(
        name=data['name'],
        slug=slug,
        plan=data.get('plan', 'free'),
        billing_email=data.get('billing_email')
    )
    
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
    """Retorna organização do usuário atual com limites e uso"""
    try:
        org = Organization.query.filter_by(id=g.organization_id).first_or_404()
        return jsonify(org.to_dict(include_limits=True)), 200
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



