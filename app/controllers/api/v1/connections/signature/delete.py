"""
Delete Signature Connection Controller.
"""

from flask import jsonify, g
from app.database import db
from app.models import DataSourceConnection, SignatureRequest

SIGNATURE_PROVIDERS = [
    'clicksign', 'docusign', 'd4sign',
    'supersign', 'zapsign', 'assineonline', 'certisign'
]


def delete_signature_connection(connection_id: str):
    """Deleta uma conexão de assinatura"""
    org_id = g.organization_id
    query = DataSourceConnection.query.filter_by(
        id=connection_id,
        organization_id=org_id
    )
    query = query.filter(DataSourceConnection.source_type.in_(SIGNATURE_PROVIDERS))
    connection = query.first_or_404()

    # Verificar se tem signature requests usando
    requests_count = SignatureRequest.query.filter_by(
        provider=connection.source_type,
        organization_id=org_id
    ).count()

    if requests_count > 0:
        return jsonify({
            'error': f'Conexão está sendo usada por {requests_count} solicitação(ões) de assinatura. Remova-as primeiro.'
        }), 400

    db.session.delete(connection)
    db.session.commit()

    return jsonify({'success': True})
