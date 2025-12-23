"""
Get Connection Controller.
"""

from flask import jsonify, g
from app.models import DataSourceConnection


def get_connection(connection_id: str):
    """Retorna detalhes de uma conexão"""
    connection = DataSourceConnection.query.filter_by(
        id=connection_id,
        organization_id=g.organization_id
    ).first_or_404()

    return jsonify(connection.to_dict(include_credentials=False))
