"""
Create Connection Controller.
"""

from flask import request, jsonify, g
from app.database import db
from app.models import DataSourceConnection
from app.utils.encryption import encrypt_credentials


def create_connection():
    """
    Cria uma nova conexão de dados.

    Body:
    {
        "source_type": "hubspot",
        "name": "HubSpot Production",
        "credentials": {
            "access_token": "..."
        },
        "config": {
            "portal_id": "123456"
        }
    }
    """
    data = request.get_json()

    required = ['source_type', 'name']
    for field in required:
        if not data.get(field):
            return jsonify({'error': f'{field} é obrigatório'}), 400

    # Criptografar credenciais
    credentials = data.get('credentials', {})
    if credentials:
        encrypted_creds = encrypt_credentials(credentials)
        credentials = {'encrypted': encrypted_creds}

    # Criar conexão
    connection = DataSourceConnection(
        organization_id=g.organization_id,
        source_type=data['source_type'],
        name=data['name'],
        credentials=credentials,
        config=data.get('config', {}),
        status='active'
    )

    db.session.add(connection)
    db.session.commit()

    return jsonify({
        'success': True,
        'connection': connection.to_dict(include_credentials=False)
    }), 201
