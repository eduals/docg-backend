"""
Test Signature Connection Controller.
"""

from flask import jsonify, g
from app.database import db
from app.models import DataSourceConnection
from app.utils.encryption import decrypt_credentials
import logging
import requests

logger = logging.getLogger(__name__)

SIGNATURE_PROVIDERS = [
    'clicksign', 'docusign', 'd4sign',
    'supersign', 'zapsign', 'assineonline', 'certisign'
]


def test_signature_connection(connection_id: str):
    """
    Testa uma conexão de assinatura validando a API key.

    Response:
    {
        "valid": true,
        "provider": "clicksign",
        "message": "API key válida"
    }
    """
    org_id = g.organization_id
    query = DataSourceConnection.query.filter_by(
        id=connection_id,
        organization_id=org_id
    )
    query = query.filter(DataSourceConnection.source_type.in_(SIGNATURE_PROVIDERS))
    connection = query.first_or_404()

    try:
        # Descriptografar API key
        if not connection.credentials or not connection.credentials.get('encrypted'):
            return jsonify({
                'valid': False,
                'provider': connection.source_type,
                'message': 'API key não configurada'
            }), 400

        decrypted = decrypt_credentials(connection.credentials['encrypted'])
        api_key = decrypted.get('api_key') or decrypted.get('clicksign_api_key')

        if not api_key:
            return jsonify({
                'valid': False,
                'provider': connection.source_type,
                'message': 'API key não encontrada'
            }), 400

        # Testar API key do provedor
        provider = connection.source_type

        if provider == 'clicksign':
            test_url = "https://sandbox.clicksign.com/api/v3/accounts"
            response = requests.get(
                test_url,
                headers={
                    "Authorization": api_key,
                    "Content-Type": "application/json"
                },
                timeout=10
            )

            if response.status_code == 200:
                connection.status = 'active'
                db.session.commit()
                return jsonify({
                    'valid': True,
                    'provider': provider,
                    'message': 'API key válida'
                })
            else:
                connection.status = 'error'
                db.session.commit()
                return jsonify({
                    'valid': False,
                    'provider': provider,
                    'message': f'API key inválida: {response.status_code}'
                }), 400
        else:
            # Para outros provedores, implementar testes específicos
            connection.status = 'pending'
            db.session.commit()
            return jsonify({
                'valid': False,
                'provider': provider,
                'message': f'Teste de conexão para {provider} ainda não implementado'
            }), 501

    except Exception as e:
        logger.error(f"Erro ao testar conexão de assinatura: {str(e)}")
        connection.status = 'error'
        db.session.commit()
        return jsonify({
            'valid': False,
            'provider': connection.source_type,
            'message': str(e)
        }), 500
