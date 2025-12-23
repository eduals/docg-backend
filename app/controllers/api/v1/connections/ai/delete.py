"""
Delete AI Connection Controller.
"""

from flask import jsonify, g
from app.database import db
from app.models import DataSourceConnection, AIGenerationMapping

AI_PROVIDERS = ['openai', 'gemini', 'anthropic']


def delete_ai_connection(connection_id: str):
    """Deleta uma conexão de IA"""
    org_id = g.organization_id
    query = DataSourceConnection.query.filter_by(
        id=connection_id,
        organization_id=org_id
    )
    query = query.filter(DataSourceConnection.source_type.in_(AI_PROVIDERS))
    connection = query.first_or_404()

    # Verificar se tem mapeamentos usando
    mappings_count = AIGenerationMapping.query.filter_by(
        ai_connection_id=connection_id
    ).count()

    if mappings_count > 0:
        return jsonify({
            'error': f'Conexão está sendo usada por {mappings_count} mapeamento(s) de IA. Remova-os primeiro.'
        }), 400

    db.session.delete(connection)
    db.session.commit()

    return jsonify({'success': True})
