"""
List Connections Controller.
"""

from flask import request, jsonify, g
from app.models import DataSourceConnection


def list_connections():
    """Lista conexões de dados da organização"""
    org_id = g.organization_id
    source_type = request.args.get('source_type')

    query = DataSourceConnection.query.filter_by(organization_id=org_id)

    if source_type:
        query = query.filter_by(source_type=source_type)

    connections = query.order_by(DataSourceConnection.created_at.desc()).all()

    return jsonify({
        'connections': [conn.to_dict() for conn in connections]
    })
