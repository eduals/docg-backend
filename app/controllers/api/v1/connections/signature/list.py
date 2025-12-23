"""
List Signature Connections Controller.
"""

from flask import jsonify, g
from app.models import DataSourceConnection

SIGNATURE_PROVIDERS = [
    'clicksign', 'docusign', 'd4sign',
    'supersign', 'zapsign', 'assineonline', 'certisign'
]


def list_signature_connections():
    """Lista conexões de assinatura da organização"""
    org_id = g.organization_id
    query = DataSourceConnection.query.filter_by(organization_id=org_id)
    query = query.filter(DataSourceConnection.source_type.in_(SIGNATURE_PROVIDERS))
    connections = query.order_by(DataSourceConnection.created_at.desc()).all()

    return jsonify({
        'connections': [conn.to_dict(include_credentials=False) for conn in connections]
    })
