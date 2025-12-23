"""
Get Signature Connection Controller.
"""

from flask import jsonify, g
from app.models import DataSourceConnection

SIGNATURE_PROVIDERS = [
    'clicksign', 'docusign', 'd4sign',
    'supersign', 'zapsign', 'assineonline', 'certisign'
]


def get_signature_connection(connection_id: str):
    """Retorna detalhes de uma conexão de assinatura"""
    org_id = g.organization_id
    query = DataSourceConnection.query.filter_by(
        id=connection_id,
        organization_id=org_id
    )
    query = query.filter(DataSourceConnection.source_type.in_(SIGNATURE_PROVIDERS))
    connection = query.first_or_404()

    return jsonify(connection.to_dict(include_credentials=False))
