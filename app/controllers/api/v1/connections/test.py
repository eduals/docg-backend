"""
Test Connection Controller.
"""

from flask import jsonify, g
from app.database import db
from app.models import DataSourceConnection
from app.services.data_sources.hubspot import HubSpotDataSource
from app.utils.encryption import decrypt_credentials
import logging

logger = logging.getLogger(__name__)


def test_connection(connection_id: str):
    """Testa uma conexão"""
    connection = DataSourceConnection.query.filter_by(
        id=connection_id,
        organization_id=g.organization_id
    ).first_or_404()

    try:
        if connection.source_type == 'hubspot':
            # Descriptografar credenciais
            if connection.credentials and connection.credentials.get('encrypted'):
                decrypted = decrypt_credentials(connection.credentials['encrypted'])
                connection.credentials = decrypted

            data_source = HubSpotDataSource(connection)
            is_valid = data_source.test_connection()

            if is_valid:
                connection.status = 'active'
                db.session.commit()
                return jsonify({
                    'success': True,
                    'message': 'Conexão testada com sucesso'
                })
            else:
                connection.status = 'error'
                db.session.commit()
                return jsonify({
                    'success': False,
                    'message': 'Falha ao testar conexão'
                }), 400
        else:
            return jsonify({
                'error': f'Tipo de fonte {connection.source_type} não suportado para teste'
            }), 400

    except Exception as e:
        logger.error(f"Erro ao testar conexão: {str(e)}")
        connection.status = 'error'
        db.session.commit()
        return jsonify({
            'error': str(e)
        }), 500
