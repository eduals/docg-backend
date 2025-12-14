"""
Rotas para gerenciar provedores de assinatura eletrônica.

Fornece endpoints para listar provedores disponíveis e testar conexões.
"""

from flask import Blueprint, request, jsonify, g
from app.utils.auth import require_auth, require_org
from app.utils.encryption import decrypt_credentials
from app.models import DataSourceConnection
from app.database import db
import logging

logger = logging.getLogger(__name__)
signature_providers_bp = Blueprint('signature_providers', __name__, url_prefix='/api/v1/signature-providers')

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

# Informações dos provedores
PROVIDER_INFO = {
    'clicksign': {
        'name': 'Clicksign',
        'description': 'Plataforma brasileira que oferece APIs e integração com WhatsApp.',
        'auth_type': 'api_key',
        'docs_url': 'https://developers.clicksign.com/'
    },
    'docusign': {
        'name': 'DocuSign',
        'description': 'Uma das líderes globais, com vasta experiência e integrações com muitos sistemas.',
        'auth_type': 'integration_key',
        'docs_url': 'https://developers.docusign.com/'
    },
    'd4sign': {
        'name': 'D4Sign',
        'description': 'Possui API própria, além de integrações com ERPs e CRMs.',
        'auth_type': 'api_key',
        'docs_url': 'https://doc.d4sign.com.br/'
    },
    'supersign': {
        'name': 'SuperSign',
        'description': 'Oferece integrações via API, além de Webhooks e plataformas como Make/Zapier.',
        'auth_type': 'api_key',
        'docs_url': 'https://supersign.com.br/'
    },
    'zapsign': {
        'name': 'ZapSign',
        'description': 'Disponibiliza APIs e integrações com plataformas como Zapier, HubSpot e Make.',
        'auth_type': 'api_key',
        'docs_url': 'https://zapsign.com.br/'
    },
    'assineonline': {
        'name': 'Assine Online',
        'description': 'Outra alternativa no mercado brasileiro, com foco em assinaturas digitais.',
        'auth_type': 'api_key',
        'docs_url': 'https://assineonline.com.br/'
    },
    'certisign': {
        'name': 'Certisign',
        'description': 'Uma das maiores empresas de certificação digital, que também oferece soluções para assinatura eletrônica.',
        'auth_type': 'api_key',
        'docs_url': 'https://www.certisign.com.br/'
    }
}


@signature_providers_bp.route('', methods=['GET'])
@require_auth
@require_org
def list_providers():
    """
    Lista provedores de assinatura disponíveis.
    
    Response:
    [
        {
            "id": "clicksign",
            "name": "Clicksign",
            "description": "...",
            "auth_type": "api_key",
            "docs_url": "..."
        },
        ...
    ]
    """
    providers = []
    for provider_id in SIGNATURE_PROVIDERS:
        info = PROVIDER_INFO.get(provider_id, {})
        providers.append({
            'id': provider_id,
            'name': info.get('name', provider_id.title()),
            'description': info.get('description', ''),
            'auth_type': info.get('auth_type', 'api_key'),
            'docs_url': info.get('docs_url', '')
        })
    
    return jsonify(providers)


@signature_providers_bp.route('/<provider_id>', methods=['GET'])
@require_auth
@require_org
def get_provider_info(provider_id):
    """
    Retorna informações detalhadas de um provedor.
    
    Response:
    {
        "id": "clicksign",
        "name": "Clicksign",
        "description": "...",
        "auth_type": "api_key",
        "docs_url": "..."
    }
    """
    provider_id = provider_id.lower()
    
    if provider_id not in SIGNATURE_PROVIDERS:
        return jsonify({
            'error': f'Provedor não suportado. Use: {", ".join(SIGNATURE_PROVIDERS)}'
        }), 400
    
    info = PROVIDER_INFO.get(provider_id, {})
    
    return jsonify({
        'id': provider_id,
        'name': info.get('name', provider_id.title()),
        'description': info.get('description', ''),
        'auth_type': info.get('auth_type', 'api_key'),
        'docs_url': info.get('docs_url', '')
    })


@signature_providers_bp.route('/<provider_id>/test', methods=['POST'])
@require_auth
@require_org
def test_provider_connection(provider_id):
    """
    Testa uma API key de um provedor de assinatura.
    
    Body:
    {
        "api_key": "sk-...",
        "environment": "sandbox" | "production"  # Opcional, apenas para ClickSign
    }
    
    Response:
    {
        "valid": true,
        "provider": "clicksign",
        "message": "API key válida"
    }
    """
    provider_id = provider_id.lower()
    
    if provider_id not in SIGNATURE_PROVIDERS:
        return jsonify({
            'valid': False,
            'error': f'Provedor não suportado. Use: {", ".join(SIGNATURE_PROVIDERS)}'
        }), 400
    
    data = request.get_json()
    api_key = data.get('api_key') if data else None
    environment = data.get('environment', 'sandbox') if data else 'sandbox'  # Default: sandbox
    
    if not api_key:
        return jsonify({
            'valid': False,
            'error': 'api_key é obrigatório no body'
        }), 400
    
    try:
        # Importar serviço de integração apropriado
        if provider_id == 'clicksign':
            import requests
            
            # Validar ambiente
            if environment not in ['sandbox', 'production']:
                return jsonify({
                    'valid': False,
                    'provider': provider_id,
                    'error': 'environment deve ser "sandbox" ou "production"'
                }), 400
            
            # Determinar URL baseada no ambiente
            if environment == 'production':
                base_url = "https://app.clicksign.com/api/v3"
            else:  # sandbox
                base_url = "https://sandbox.clicksign.com/api/v3"
            
            # Usar endpoint de listagem de envelopes para testar
            # Este endpoint é conhecido por funcionar (usado em ClickSignIntegration)
            test_url = f"{base_url}/envelopes"
            
            logger.info(f"Testando conexão ClickSign - Ambiente: {environment}, URL: {test_url}")
            
            try:
                response = requests.get(
                    test_url,
                    headers={
                        "Authorization": api_key,
                        "Content-Type": "application/json"
                    },
                    params={"page": 1, "per_page": 1},  # Limitar a 1 resultado para teste rápido
                    timeout=10
                )
                
                logger.info(f"Resposta ClickSign - Status: {response.status_code}")
                
                # Tratar diferentes códigos de status
                if response.status_code == 200:
                    # Verificar se a resposta é válida
                    try:
                        data = response.json()
                        logger.info(f"Resposta ClickSign válida: {type(data)}")
                        return jsonify({
                            'valid': True,
                            'provider': provider_id,
                            'message': 'API key válida'
                        })
                    except ValueError:
                        # Resposta não é JSON válido
                        logger.error(f"Resposta ClickSign não é JSON válido: {response.text[:200]}")
                        return jsonify({
                            'valid': False,
                            'provider': provider_id,
                            'message': 'Resposta inválida da API do ClickSign'
                        }), 400
                elif response.status_code == 401:
                    logger.warning(f"ClickSign retornou 401 - API key inválida")
                    return jsonify({
                        'valid': False,
                        'provider': provider_id,
                        'message': 'API key inválida ou expirada'
                    }), 400
                elif response.status_code == 404:
                    logger.error(f"ClickSign retornou 404 - Endpoint não encontrado")
                    return jsonify({
                        'valid': False,
                        'provider': provider_id,
                        'message': 'Endpoint não encontrado. Verifique a configuração da API.'
                    }), 400
                else:
                    # Outros erros
                    error_msg = f'Erro ao testar conexão: {response.status_code}'
                    try:
                        error_data = response.json()
                        if 'errors' in error_data:
                            error_msg = error_data['errors'][0].get('detail', error_msg)
                        elif 'error' in error_data:
                            error_msg = error_data.get('error', error_msg)
                    except:
                        error_msg = f'Erro ao testar conexão: {response.status_code} - {response.text[:200]}'
                    
                    logger.error(f"ClickSign retornou erro {response.status_code}: {error_msg}")
                    return jsonify({
                        'valid': False,
                        'provider': provider_id,
                        'message': error_msg
                    }), 400
                    
            except requests.exceptions.Timeout:
                logger.error("Timeout ao conectar com a API do ClickSign")
                return jsonify({
                    'valid': False,
                    'provider': provider_id,
                    'message': 'Timeout ao conectar com a API do ClickSign'
                }), 500
            except requests.exceptions.RequestException as e:
                logger.error(f"Erro de requisição ao testar ClickSign: {str(e)}")
                return jsonify({
                    'valid': False,
                    'provider': provider_id,
                    'message': f'Erro de conexão: {str(e)}'
                }), 500
        
        # Para outros provedores, implementar testes específicos
        # Por enquanto, retornar que precisa implementação
        return jsonify({
            'valid': False,
            'provider': provider_id,
            'message': f'Teste de conexão para {provider_id} ainda não implementado'
        }), 501
        
    except Exception as e:
        logger.error(f"Erro ao testar conexão {provider_id}: {str(e)}")
        return jsonify({
            'valid': False,
            'provider': provider_id,
            'message': f'Erro ao testar conexão: {str(e)}'
        }), 500

