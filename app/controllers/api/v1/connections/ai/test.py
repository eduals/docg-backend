"""
Test AI Connection Controller.
"""

from flask import jsonify, g
from app.database import db
from app.models import DataSourceConnection
from app.utils.encryption import decrypt_credentials
import logging

logger = logging.getLogger(__name__)

AI_PROVIDERS = ['openai', 'gemini', 'anthropic']


def test_ai_connection(connection_id: str):
    """
    Testa uma conexão de IA validando a API key.

    Response:
    {
        "valid": true,
        "provider": "openai",
        "message": "API key válida"
    }
    """
    org_id = g.organization_id
    query = DataSourceConnection.query.filter_by(
        id=connection_id,
        organization_id=org_id
    )
    query = query.filter(DataSourceConnection.source_type.in_(AI_PROVIDERS))
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
        api_key = decrypted.get('api_key')

        if not api_key:
            return jsonify({
                'valid': False,
                'provider': connection.source_type,
                'message': 'API key não encontrada'
            }), 400

        # Testar com o serviço de LLM
        from app.services.ai import LLMService
        llm_service = LLMService()
        result = llm_service.validate_api_key(connection.source_type, api_key)

        # Atualizar status da conexão
        if result['valid']:
            connection.status = 'active'
        else:
            connection.status = 'error'
        db.session.commit()

        return jsonify(result)

    except Exception as e:
        logger.error(f"Erro ao testar conexão AI: {str(e)}")
        connection.status = 'error'
        db.session.commit()
        return jsonify({
            'valid': False,
            'provider': connection.source_type,
            'message': str(e)
        }), 500
