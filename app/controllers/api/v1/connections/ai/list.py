"""
List AI Connections Controller.
"""

from flask import jsonify, g
from app.models import DataSourceConnection

AI_PROVIDERS = ['openai', 'gemini', 'anthropic']


def list_ai_connections():
    """Lista conexões de IA da organização"""
    org_id = g.organization_id
    query = DataSourceConnection.query.filter_by(organization_id=org_id)
    query = query.filter(DataSourceConnection.source_type.in_(AI_PROVIDERS))
    connections = query.order_by(DataSourceConnection.created_at.desc()).all()

    return jsonify({
        'connections': [conn.to_dict(include_credentials=False) for conn in connections]
    })
