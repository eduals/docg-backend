"""
Update Connection Controller.
"""

from flask import request, jsonify, g
from app.database import db
from app.models import DataSourceConnection
from app.utils.encryption import encrypt_credentials


def update_connection(connection_id: str):
    """Atualiza uma conexão"""
    connection = DataSourceConnection.query.filter_by(
        id=connection_id,
        organization_id=g.organization_id
    ).first_or_404()

    data = request.get_json()

    # Atualizar campos permitidos
    if 'name' in data:
        connection.name = data['name']

    if 'credentials' in data:
        encrypted_creds = encrypt_credentials(data['credentials'])
        connection.credentials = {'encrypted': encrypted_creds}

    if 'config' in data:
        connection.config = data['config']

    if 'status' in data:
        connection.status = data['status']

    db.session.commit()

    return jsonify({
        'success': True,
        'connection': connection.to_dict(include_credentials=False)
    })
