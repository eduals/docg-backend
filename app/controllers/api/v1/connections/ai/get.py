"""
Get AI Connection Controller.
"""

from flask import jsonify, g
from app.models import DataSourceConnection

AI_PROVIDERS = ['openai', 'gemini', 'anthropic']


def get_ai_connection(connection_id: str):
    """Retorna detalhes de uma conexão de IA"""
    org_id = g.organization_id
    query = DataSourceConnection.query.filter_by(
        id=connection_id,
        organization_id=org_id
    )
    query = query.filter(DataSourceConnection.source_type.in_(AI_PROVIDERS))
    connection = query.first_or_404()

    return jsonify(connection.to_dict(include_credentials=False))
