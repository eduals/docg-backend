from flask import Blueprint, request, jsonify, g
from app.database import db
from app.models import User
from app.utils.auth import require_auth, require_org, require_admin
import logging

logger = logging.getLogger(__name__)
users_bp = Blueprint('users', __name__, url_prefix='/api/v1/users')


@users_bp.route('', methods=['GET'])
@require_auth
@require_org
def list_users():
    """Lista usuários da organização"""
    org_id = g.organization_id
    
    users = User.query.filter_by(organization_id=org_id).all()
    
    return jsonify({
        'users': [user.to_dict() for user in users]
    })


@users_bp.route('/me', methods=['GET'])
@require_auth
@require_org
def get_current_user():
    """Retorna dados do usuário atual baseado no email"""
    user_email = request.headers.get('X-User-Email') or request.args.get('user_email')
    
    if not user_email:
        return jsonify({'error': 'user_email é obrigatório'}), 400
    
    user = User.query.filter_by(
        email=user_email,
        organization_id=g.organization_id
    ).first()
    
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404
    
    return jsonify(user.to_dict())


@users_bp.route('/<user_id>', methods=['GET'])
@require_auth
@require_org
def get_user(user_id):
    """Retorna detalhes de um usuário"""
    user = User.query.filter_by(
        id=user_id,
        organization_id=g.organization_id
    ).first_or_404()
    
    return jsonify(user.to_dict())


@users_bp.route('', methods=['POST'])
@require_auth
@require_org
@require_admin
def create_user():
    """
    Cria um novo usuário.
    
    Body:
    {
        "email": "user@example.com",
        "name": "John Doe",
        "role": "user",
        "hubspot_user_id": "123"
    }
    """
    data = request.get_json()
    
    required = ['email']
    for field in required:
        if not data.get(field):
            return jsonify({'error': f'{field} é obrigatório'}), 400
    
    # Verificar se email já existe na organização
    existing = User.query.filter_by(
        organization_id=g.organization_id,
        email=data['email']
    ).first()
    
    if existing:
        return jsonify({'error': 'Email já cadastrado nesta organização'}), 400
    
    # Criar usuário
    user = User(
        organization_id=g.organization_id,
        email=data['email'],
        name=data.get('name'),
        role=data.get('role', 'user'),
        hubspot_user_id=data.get('hubspot_user_id'),
        google_user_id=data.get('google_user_id')
    )
    
    db.session.add(user)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'user': user.to_dict()
    }), 201


@users_bp.route('/<user_id>', methods=['PUT'])
@require_auth
@require_org
@require_admin
def update_user(user_id):
    """Atualiza um usuário"""
    user = User.query.filter_by(
        id=user_id,
        organization_id=g.organization_id
    ).first_or_404()
    
    data = request.get_json()
    
    # Atualizar campos permitidos
    if 'name' in data:
        user.name = data['name']
    
    if 'role' in data:
        user.role = data['role']
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'user': user.to_dict()
    })


@users_bp.route('/<user_id>', methods=['DELETE'])
@require_auth
@require_org
@require_admin
def delete_user(user_id):
    """Deleta um usuário"""
    user = User.query.filter_by(
        id=user_id,
        organization_id=g.organization_id
    ).first_or_404()
    
    # Não permitir deletar último admin
    if user.is_admin():
        admin_count = User.query.filter_by(
            organization_id=g.organization_id,
            role='admin'
        ).count()
        
        if admin_count <= 1:
            return jsonify({
                'error': 'Não é possível deletar o último administrador'
            }), 400
    
    db.session.delete(user)
    db.session.commit()
    
    return jsonify({'success': True})

