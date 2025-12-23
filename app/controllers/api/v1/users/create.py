"""
Create User Controller.
"""

from flask import request, jsonify, g
from app.database import db
from app.models import User


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
