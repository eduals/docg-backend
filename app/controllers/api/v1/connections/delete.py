"""
Delete Connection Controller.
"""

from flask import jsonify, g
from app.database import db
from app.models import DataSourceConnection


def delete_connection(connection_id: str):
    """Deleta uma conexão"""
    connection = DataSourceConnection.query.filter_by(
        id=connection_id,
        organization_id=g.organization_id
    ).first_or_404()

    # Verificar se tem workflows usando
    if connection.workflows.count() > 0:
        return jsonify({
            'error': 'Conexão está sendo usada por workflows. Remova os workflows primeiro.'
        }), 400

    db.session.delete(connection)
    db.session.commit()

    return jsonify({'success': True})
