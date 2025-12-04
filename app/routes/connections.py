from flask import Blueprint, request, jsonify, g
from app.database import db
from app.models import DataSourceConnection
from app.services.data_sources.hubspot import HubSpotDataSource
from app.utils.auth import require_auth, require_org, require_admin
from app.utils.encryption import encrypt_credentials, decrypt_credentials
import logging

logger = logging.getLogger(__name__)
ai_logger = logging.getLogger('docugen.ai')
connections_bp = Blueprint('connections', __name__, url_prefix='/api/v1/connections')

# Provedores de IA suportados
AI_PROVIDERS = ['openai', 'gemini', 'anthropic']

# Provedores de assinatura suportados
SIGNATURE_PROVIDERS = [
    'clicksign',
    'docusign',
    'd4sign',
    'supersign',
    'zapsign',
    'assineonline',
    'certisign'
]


@connections_bp.route('', methods=['GET'])
@require_auth
@require_org
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


@connections_bp.route('/<connection_id>', methods=['GET'])
@require_auth
@require_org
def get_connection(connection_id):
    """Retorna detalhes de uma conexão"""
    connection = DataSourceConnection.query.filter_by(
        id=connection_id,
        organization_id=g.organization_id
    ).first_or_404()
    
    return jsonify(connection.to_dict(include_credentials=False))


@connections_bp.route('', methods=['POST'])
@require_auth
@require_org
@require_admin
def create_connection():
    """
    Cria uma nova conexão de dados.
    
    Body:
    {
        "source_type": "hubspot",
        "name": "HubSpot Production",
        "credentials": {
            "access_token": "..."
        },
        "config": {
            "portal_id": "123456"
        }
    }
    """
    data = request.get_json()
    
    required = ['source_type', 'name']
    for field in required:
        if not data.get(field):
            return jsonify({'error': f'{field} é obrigatório'}), 400
    
    # Criptografar credenciais
    credentials = data.get('credentials', {})
    if credentials:
        encrypted_creds = encrypt_credentials(credentials)
        credentials = {'encrypted': encrypted_creds}
    
    # Criar conexão
    connection = DataSourceConnection(
        organization_id=g.organization_id,
        source_type=data['source_type'],
        name=data['name'],
        credentials=credentials,
        config=data.get('config', {}),
        status='active'
    )
    
    db.session.add(connection)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'connection': connection.to_dict(include_credentials=False)
    }), 201


@connections_bp.route('/<connection_id>', methods=['PUT'])
@require_auth
@require_org
@require_admin
def update_connection(connection_id):
    """Atualiza uma conexão"""
    connection = DataSourceConnection.query.filter_by(
        id=connection_id,
        organization_id=g.organization_id
    ).first_or_404()
    
    data = request.get_json()
    
    # Atualizar campos permitidos
    if 'name' in data:
        connection.name = data['name']
    
    if 'credentials' in data:
        encrypted_creds = encrypt_credentials(data['credentials'])
        connection.credentials = {'encrypted': encrypted_creds}
    
    if 'config' in data:
        connection.config = data['config']
    
    if 'status' in data:
        connection.status = data['status']
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'connection': connection.to_dict(include_credentials=False)
    })


@connections_bp.route('/<connection_id>/test', methods=['POST'])
@require_auth
@require_org
def test_connection(connection_id):
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


@connections_bp.route('/<connection_id>', methods=['DELETE'])
@require_auth
@require_org
@require_admin
def delete_connection(connection_id):
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


# ==================== AI CONNECTION ENDPOINTS ====================

@connections_bp.route('/ai', methods=['POST'])
@require_auth
@require_org
@require_admin
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
        status='pending'  # Será 'active' após teste
    )
    
    db.session.add(connection)
    db.session.commit()
    
    ai_logger.info(f"[AI] Conexão criada - provider={provider}, org={g.organization_id}")
    
    return jsonify({
        'success': True,
        'connection': connection.to_dict(include_credentials=False)
    }), 201


@connections_bp.route('/ai', methods=['GET'])
@require_auth
@require_org
def list_ai_connections():
    """Lista conexões de IA da organização"""
    org_id = g.organization_id
    query = DataSourceConnection.query.filter_by(organization_id=org_id)
    query = query.filter(DataSourceConnection.source_type.in_(AI_PROVIDERS))
    connections = query.order_by(DataSourceConnection.created_at.desc()).all()
    print("connections to dict: ", [conn.to_dict(include_credentials=False) for conn in connections])
    
    return jsonify({
        'connections': [conn.to_dict(include_credentials=False) for conn in connections]
    })


@connections_bp.route('/ai/<connection_id>', methods=['GET'])
@require_auth
@require_org
def get_ai_connection(connection_id):
    """Retorna detalhes de uma conexão de IA"""
    org_id = g.organization_id
    query = DataSourceConnection.query.filter_by(
        id=connection_id,
        organization_id=org_id
    )
    query = query.filter(DataSourceConnection.source_type.in_(AI_PROVIDERS))
    connection = query.first_or_404()
    
    return jsonify(connection.to_dict(include_credentials=False))


@connections_bp.route('/ai/<connection_id>', methods=['PATCH'])
@require_auth
@require_org
@require_admin
def update_ai_connection(connection_id):
    """
    Atualiza uma conexão de IA.
    
    Body:
    {
        "api_key": "sk-new...",  # opcional
        "name": "Novo nome"  # opcional
    }
    """
    org_id = g.organization_id
    query = DataSourceConnection.query.filter_by(
        id=connection_id,
        organization_id=org_id
    )
    query = query.filter(DataSourceConnection.source_type.in_(AI_PROVIDERS))
    connection = query.first_or_404()
    
    data = request.get_json()
    
    if 'name' in data:
        connection.name = data['name']
    
    if 'api_key' in data:
        encrypted_creds = encrypt_credentials({'api_key': data['api_key']})
        connection.credentials = {'encrypted': encrypted_creds}
        connection.status = 'pending'  # Precisa testar novamente
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'connection': connection.to_dict(include_credentials=False)
    })


@connections_bp.route('/ai/<connection_id>', methods=['DELETE'])
@require_auth
@require_org
@require_admin
def delete_ai_connection(connection_id):
    """Deleta uma conexão de IA"""
    org_id = g.organization_id
    query = DataSourceConnection.query.filter_by(
        id=connection_id,
        organization_id=org_id
    )
    query = query.filter(DataSourceConnection.source_type.in_(AI_PROVIDERS))
    connection = query.first_or_404()
    
    # Verificar se tem mapeamentos usando
    from app.models import AIGenerationMapping
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


@connections_bp.route('/ai/<connection_id>/test', methods=['POST'])
@require_auth
@require_org
def test_ai_connection(connection_id):
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


# ==================== SIGNATURE CONNECTION ENDPOINTS ====================

@connections_bp.route('/signature', methods=['POST'])
@require_auth
@require_org
@require_admin
def create_signature_connection():
    """
    Cria uma nova conexão de provedor de assinatura (BYOK - Bring Your Own Key).
    
    Body:
    {
        "provider": "clicksign",  # clicksign, docusign, d4sign, etc
        "api_key": "sk-...",
        "name": "ClickSign Production"  # opcional
    }
    """
    data = request.get_json()
    
    # Validar provider
    provider = data.get('provider', '').lower()
    if provider not in SIGNATURE_PROVIDERS:
        return jsonify({
            'error': f'Provedor não suportado. Use: {", ".join(SIGNATURE_PROVIDERS)}'
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
            'error': f'Já existe uma conexão para {provider}. Use PATCH para atualizar.'
        }), 409
    
    # Criptografar API key
    encrypted_creds = encrypt_credentials({'api_key': api_key})
    
    # Criar conexão
    connection = DataSourceConnection(
        organization_id=g.organization_id,
        source_type=provider,
        name=name,
        credentials={'encrypted': encrypted_creds},
        config={'provider_type': 'signature'},
        status='pending'  # Será 'active' após teste
    )
    
    db.session.add(connection)
    db.session.commit()
    
    logger.info(f"[Signature] Conexão criada - provider={provider}, org={g.organization_id}")
    
    return jsonify({
        'success': True,
        'connection': connection.to_dict(include_credentials=False)
    }), 201


@connections_bp.route('/signature', methods=['GET'])
@require_auth
@require_org
def list_signature_connections():
    """Lista conexões de assinatura da organização"""
    org_id = g.organization_id
    query = DataSourceConnection.query.filter_by(organization_id=org_id)
    query = query.filter(DataSourceConnection.source_type.in_(SIGNATURE_PROVIDERS))
    connections = query.order_by(DataSourceConnection.created_at.desc()).all()
    
    return jsonify({
        'connections': [conn.to_dict(include_credentials=False) for conn in connections]
    })


@connections_bp.route('/signature/<connection_id>', methods=['GET'])
@require_auth
@require_org
def get_signature_connection(connection_id):
    """Retorna detalhes de uma conexão de assinatura"""
    org_id = g.organization_id
    query = DataSourceConnection.query.filter_by(
        id=connection_id,
        organization_id=org_id
    )
    query = query.filter(DataSourceConnection.source_type.in_(SIGNATURE_PROVIDERS))
    connection = query.first_or_404()
    
    return jsonify(connection.to_dict(include_credentials=False))


@connections_bp.route('/signature/<connection_id>', methods=['PATCH'])
@require_auth
@require_org
@require_admin
def update_signature_connection(connection_id):
    """
    Atualiza uma conexão de assinatura.
    
    Body:
    {
        "api_key": "sk-new...",  # opcional
        "name": "Novo nome"  # opcional
    }
    """
    org_id = g.organization_id
    query = DataSourceConnection.query.filter_by(
        id=connection_id,
        organization_id=org_id
    )
    query = query.filter(DataSourceConnection.source_type.in_(SIGNATURE_PROVIDERS))
    connection = query.first_or_404()
    
    data = request.get_json()
    
    if 'name' in data:
        connection.name = data['name']
    
    if 'api_key' in data:
        encrypted_creds = encrypt_credentials({'api_key': data['api_key']})
        connection.credentials = {'encrypted': encrypted_creds}
        connection.status = 'pending'  # Precisa testar novamente
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'connection': connection.to_dict(include_credentials=False)
    })


@connections_bp.route('/signature/<connection_id>', methods=['DELETE'])
@require_auth
@require_org
@require_admin
def delete_signature_connection(connection_id):
    """Deleta uma conexão de assinatura"""
    org_id = g.organization_id
    query = DataSourceConnection.query.filter_by(
        id=connection_id,
        organization_id=org_id
    )
    query = query.filter(DataSourceConnection.source_type.in_(SIGNATURE_PROVIDERS))
    connection = query.first_or_404()
    
    # Verificar se tem signature requests usando
    from app.models import SignatureRequest
    requests_count = SignatureRequest.query.filter_by(
        provider=connection.source_type,
        organization_id=org_id
    ).count()
    
    if requests_count > 0:
        return jsonify({
            'error': f'Conexão está sendo usada por {requests_count} solicitação(ões) de assinatura. Remova-as primeiro.'
        }), 400
    
    db.session.delete(connection)
    db.session.commit()
    
    return jsonify({'success': True})


@connections_bp.route('/signature/<connection_id>/test', methods=['POST'])
@require_auth
@require_org
def test_signature_connection(connection_id):
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
        # Suporta tanto 'api_key' (novo formato) quanto 'clicksign_api_key' (legado)
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
            import requests
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

