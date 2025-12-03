"""
Middleware de autenticação para requisições do HubSpot.
"""

from functools import wraps
from flask import request, g, jsonify
import requests
import logging
import os

logger = logging.getLogger(__name__)


def require_hubspot_auth(f):
    """
    Middleware que valida token OAuth do HubSpot.
    Armazena informações do HubSpot em g.hubspot_context.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Obter token do header
        auth_header = request.headers.get('Authorization', '')
        token = auth_header.replace('Bearer ', '') if auth_header.startswith('Bearer ') else ''
        
        # Também aceitar token no header customizado
        if not token:
            token = request.headers.get('X-HubSpot-Access-Token', '')
        
        if not token:
            return jsonify({'error': 'Token não fornecido'}), 401
        
        try:
            # Validar token com HubSpot
            response = requests.get(
                f'https://api.hubapi.com/oauth/v1/access-tokens/{token}'
            )
            
            if response.status_code != 200:
                logger.warning(f'Token HubSpot inválido: {response.status_code}')
                return jsonify({'error': 'Token inválido'}), 401
            
            token_info = response.json()
            
            # Armazenar informações no contexto da requisição
            g.hubspot_context = {
                'hub_id': token_info.get('hub_id'),
                'user_id': token_info.get('user_id'),
                'user_email': token_info.get('user'),
                'scopes': token_info.get('scopes', []),
                'token': token
            }
            
            # Buscar organização associada ao hub_id
            # TODO: Implementar busca da organização
            # from app.models import Organization
            # org = Organization.query.filter_by(hubspot_hub_id=token_info.get('hub_id')).first()
            # if org:
            #     g.organization_id = str(org.id)
            
            return f(*args, **kwargs)
            
        except Exception as e:
            logger.exception(f'Erro ao validar token HubSpot: {str(e)}')
            return jsonify({'error': 'Erro ao validar token'}), 500
    
    return decorated_function


def optional_hubspot_auth(f):
    """
    Middleware opcional de autenticação HubSpot.
    Não falha se o token não for fornecido, mas valida se for.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        token = auth_header.replace('Bearer ', '') if auth_header.startswith('Bearer ') else ''
        
        if not token:
            token = request.headers.get('X-HubSpot-Access-Token', '')
        
        g.hubspot_context = None
        
        if token:
            try:
                response = requests.get(
                    f'https://api.hubapi.com/oauth/v1/access-tokens/{token}'
                )
                
                if response.status_code == 200:
                    token_info = response.json()
                    g.hubspot_context = {
                        'hub_id': token_info.get('hub_id'),
                        'user_id': token_info.get('user_id'),
                        'user_email': token_info.get('user'),
                        'scopes': token_info.get('scopes', []),
                        'token': token
                    }
            except Exception as e:
                logger.warning(f'Erro ao validar token HubSpot (opcional): {str(e)}')
        
        return f(*args, **kwargs)
    
    return decorated_function


def verify_hubspot_signature(f):
    """
    Middleware que verifica a assinatura das requisições do HubSpot.
    Usado para validar webhooks e workflow actions.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        signature = request.headers.get('X-HubSpot-Signature')
        signature_version = request.headers.get('X-HubSpot-Signature-Version', 'v1')
        
        if not signature:
            # Em desenvolvimento, permitir sem assinatura
            if os.getenv('FLASK_ENV') == 'development':
                logger.warning('Requisição HubSpot sem assinatura (permitido em desenvolvimento)')
                return f(*args, **kwargs)
            return jsonify({'error': 'Assinatura não fornecida'}), 401
        
        client_secret = os.getenv('HUBSPOT_CLIENT_SECRET')
        if not client_secret:
            logger.error('HUBSPOT_CLIENT_SECRET não configurado')
            return jsonify({'error': 'Configuração inválida'}), 500
        
        # Verificar assinatura
        import hashlib
        import hmac
        
        if signature_version == 'v1':
            # v1: SHA256(client_secret + request_body)
            body = request.get_data(as_text=True)
            expected = hashlib.sha256((client_secret + body).encode()).hexdigest()
        elif signature_version == 'v2':
            # v2: HMAC-SHA256
            body = request.get_data()
            expected = hmac.new(
                client_secret.encode(),
                body,
                hashlib.sha256
            ).hexdigest()
        else:
            return jsonify({'error': f'Versão de assinatura não suportada: {signature_version}'}), 400
        
        if not hmac.compare_digest(signature, expected):
            logger.warning('Assinatura HubSpot inválida')
            return jsonify({'error': 'Assinatura inválida'}), 401
        
        return f(*args, **kwargs)
    
    return decorated_function

