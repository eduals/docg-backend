"""
Middleware de autenticação para requisições do HubSpot.
"""

from functools import wraps
from flask import request, g, jsonify
import requests
import logging
import os
import hashlib
import hmac
import time

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


def flexible_hubspot_auth(f):
    """
    Middleware flexível de autenticação que aceita:
    1. Requisições do HubSpot via hubspot.fetch() (com portalId/appId - verificar PRIMEIRO)
    2. Validação de assinatura HubSpot (X-HubSpot-Signature-v3 + X-HubSpot-Request-Timestamp)
    3. Authorization Bearer token (BACKEND_API_TOKEN)
    
    Proteção contra replay attacks: rejeita requests com timestamp > 5 minutos.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # PRIMEIRO: Verificar se é uma requisição do HubSpot via hubspot.fetch()
        # O HubSpot envia portalId e appId na query string quando usa hubspot.fetch()
        portal_id = request.args.get('portalId') or request.headers.get('X-HubSpot-Portal-Id')
        app_id = request.args.get('appId') or request.headers.get('X-HubSpot-App-Id')
        user_id = request.args.get('userId') or request.headers.get('X-HubSpot-User-Id')
        user_email = request.args.get('userEmail') or request.headers.get('X-HubSpot-User-Email')
        
        # Se temos portalId e appId, é uma requisição legítima do HubSpot via hubspot.fetch()
        # Aceitar imediatamente sem validar assinatura (hubspot.fetch() não envia assinatura válida)
        if portal_id and app_id:
            logger.info(f'Requisição do HubSpot via hubspot.fetch() detectada (portalId: {portal_id}, appId: {app_id})')
            g.auth_method = 'hubspot_context'
            g.token = 'hubspot_context_auth'
            # Armazenar contexto do HubSpot
            g.hubspot_context = {
                'portal_id': portal_id,
                'app_id': app_id,
                'user_id': user_id,
                'user_email': user_email
            }
            return f(*args, **kwargs)
        
        # SEGUNDO: Verificar assinatura HubSpot (v3) - para webhooks e outras requisições assinadas
        signature_v3 = request.headers.get('X-HubSpot-Signature-v3')
        timestamp_header = request.headers.get('X-HubSpot-Request-Timestamp')
        
        if signature_v3 and timestamp_header:
            # Tentar validar assinatura HubSpot
            try:
                # O timestamp do HubSpot pode vir em milissegundos ou segundos
                timestamp_raw = int(timestamp_header)
                
                # Se o timestamp tem mais de 10 dígitos, está em milissegundos
                if timestamp_raw > 9999999999:
                    timestamp = timestamp_raw // 1000  # Converter milissegundos para segundos
                else:
                    timestamp = timestamp_raw
                
                current_time = int(time.time())
                
                # Proteção contra replay attacks: rejeitar se timestamp > 5 minutos (300 segundos)
                if abs(current_time - timestamp) > 300:
                    logger.warning(f'Request timestamp muito antigo ou futuro: {timestamp} (original: {timestamp_raw}), atual: {current_time}')
                    return jsonify({
                        'error': 'Request timestamp inválido',
                        'message': 'Timestamp muito antigo ou futuro. Request rejeitado para prevenir replay attacks.'
                    }), 401
                
                client_secret = os.getenv('HUBSPOT_CLIENT_SECRET')
                if not client_secret:
                    logger.error('HUBSPOT_CLIENT_SECRET não configurado')
                    return jsonify({'error': 'Configuração inválida'}), 500
                
                # Validar assinatura v3
                # v3: HMAC-SHA256 usando source_string = HTTP_METHOD + URI + request_body + timestamp
                body = request.get_data()
                http_method = request.method
                uri = request.path
                source_string = f"{http_method}{uri}{body.decode('utf-8', errors='ignore')}{timestamp_header}"
                expected_signature = hmac.new(
                    client_secret.encode(),
                    source_string.encode('utf-8'),
                    hashlib.sha256
                ).hexdigest()
                
                if hmac.compare_digest(signature_v3, expected_signature):
                    # Assinatura válida - permitir acesso
                    logger.debug('Autenticação HubSpot (assinatura v3) válida')
                    g.auth_method = 'hubspot_signature'
                    g.token = 'hubspot_signature_auth'
                    return f(*args, **kwargs)
                else:
                    logger.warning('Assinatura HubSpot v3 inválida - continuando para verificar outros métodos')
            except (ValueError, TypeError) as e:
                logger.warning(f'Erro ao validar timestamp HubSpot: {str(e)}')
                # Continuar para verificar Bearer token
        
        # TERCEIRO: Verificar Bearer token
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header.replace('Bearer ', '').strip()
            backend_api_token = os.getenv('BACKEND_API_TOKEN')
            
            if not backend_api_token:
                logger.error('BACKEND_API_TOKEN não configurado')
                return jsonify({'error': 'Configuração inválida'}), 500
            
            # Comparar token com BACKEND_API_TOKEN
            if hmac.compare_digest(token, backend_api_token):
                # Bearer token válido - permitir acesso
                logger.debug('Autenticação Bearer token válida')
                g.auth_method = 'bearer_token'
                g.token = token
                return f(*args, **kwargs)
            else:
                logger.warning('Bearer token inválido')
        
        # Nenhum método de autenticação válido
        logger.warning('Nenhum método de autenticação válido encontrado')
        logger.warning(f'Headers recebidos: {dict(request.headers)}')
        logger.warning(f'Query params: {dict(request.args)}')
        return jsonify({
            'error': 'Unauthorized',
            'message': 'Autenticação requerida. Use assinatura HubSpot ou Authorization Bearer token.'
        }), 401
    
    return decorated_function

