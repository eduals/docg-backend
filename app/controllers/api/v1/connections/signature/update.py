"""
Update Signature Connection Controller.
"""

from flask import request, jsonify, g
from app.database import db
from app.models import DataSourceConnection
from app.utils.encryption import encrypt_credentials

SIGNATURE_PROVIDERS = [
    'clicksign', 'docusign', 'd4sign',
    'supersign', 'zapsign', 'assineonline', 'certisign'
]


def update_signature_connection(connection_id: str):
    """
    Atualiza uma conexão de assinatura.

    Body:
    {
        "api_key": "sk-new...",
        "name": "Novo nome"
    }
    """
    org_id = g.organization_id
    query = DataSourceConnection.query.filter_by(
        id=connection_id,
        organization_id=org_id
    )
    query = query.filter(DataSourceConnection.source_type.in_(SIGNATURE_PROVIDERS))
    connection = query.first_or_404()

    data = request.get_json()

    if 'name' in data:
        connection.name = data['name']

    if 'api_key' in data:
        encrypted_creds = encrypt_credentials({'api_key': data['api_key']})
        connection.credentials = {'encrypted': encrypted_creds}
        connection.status = 'pending'

    db.session.commit()

    return jsonify({
        'success': True,
        'connection': connection.to_dict(include_credentials=False)
    })
