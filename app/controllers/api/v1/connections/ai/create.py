"""
Create AI Connection Controller.
"""

from flask import request, jsonify, g
from app.database import db
from app.models import DataSourceConnection
from app.utils.encryption import encrypt_credentials
import logging

logger = logging.getLogger(__name__)
ai_logger = logging.getLogger('docugen.ai')

AI_PROVIDERS = ['openai', 'gemini', 'anthropic']


def create_ai_connection():
    """
    Cria uma nova conexão de IA (BYOK - Bring Your Own Key).

    Body:
    {
        "provider": "openai",  # openai, gemini, anthropic
        "api_key": "sk-...",
        "name": "OpenAI Production"  # opcional
    }
    """
    data = request.get_json()

    # Validar provider
    provider = data.get('provider', '').lower()
    if provider not in AI_PROVIDERS:
        return jsonify({
            'error': f'Provedor não suportado. Use: {", ".join(AI_PROVIDERS)}'
        }), 400

    # Validar API key
    api_key = data.get('api_key')
    if not api_key:
        return jsonify({'error': 'api_key é obrigatório'}), 400

    # Nome padrão se não fornecido
    name = data.get('name', f'{provider.title()} Connection')

    # Verificar se já existe conexão para este provider
    existing = DataSourceConnection.query.filter_by(
        organization_id=g.organization_id,
        source_type=provider
    ).first()

    if existing:
        return jsonify({
            'error': f'Já existe uma conexão para {provider}. Use PUT para atualizar.'
        }), 409

    # Criptografar API key
    encrypted_creds = encrypt_credentials({'api_key': api_key})

    # Criar conexão
    connection = DataSourceConnection(
        organization_id=g.organization_id,
        source_type=provider,
        name=name,
        credentials={'encrypted': encrypted_creds},
        config={'provider_type': 'ai'},
        status='pending'
    )

    db.session.add(connection)
    db.session.commit()

    ai_logger.info(f"[AI] Conexão criada - provider={provider}, org={g.organization_id}")

    return jsonify({
        'success': True,
        'connection': connection.to_dict(include_credentials=False)
    }), 201
