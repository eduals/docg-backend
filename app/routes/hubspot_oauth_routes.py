"""
Rotas de OAuth do HubSpot.
Gerencia autenticação e autorização com o HubSpot.
"""

from flask import Blueprint, request, jsonify, redirect
import requests
import os
import logging
from urllib.parse import quote, unquote

logger = logging.getLogger(__name__)

hubspot_oauth_bp = Blueprint('hubspot_oauth', __name__, url_prefix='/api/v1/hubspot-oauth')


@hubspot_oauth_bp.route('/authorize', methods=['GET'])
def authorize():
    """
    Inicia o fluxo de autorização OAuth do HubSpot.
    Retorna a URL para o usuário autorizar o app.
    """
    client_id = os.getenv('HUBSPOT_CLIENT_ID')
    
    if not client_id:
        logger.error('HUBSPOT_CLIENT_ID não configurado')
        return jsonify({'error': 'HUBSPOT_CLIENT_ID não configurado'}), 500
    
    # Usar localhost como padrão para desenvolvimento
    redirect_uri = os.getenv('HUBSPOT_REDIRECT_URI', 'http://localhost:5000/api/v1/hubspot-oauth/callback')
    
    scopes = [
        'oauth',
        'crm.objects.contacts.read',
        'crm.objects.contacts.write',
        'crm.objects.deals.read',
        'crm.objects.deals.write',
        'crm.objects.companies.read',
        'crm.objects.companies.write',
        'crm.objects.tickets.read',
        'crm.objects.tickets.write',
        'crm.objects.quotes.read',
        'crm.objects.quotes.write',
        'crm.objects.line_items.read',
        'crm.objects.line_items.write',
        'files',
        'timeline'
    ]
    
    scope_string = ' '.join(scopes)
    
    # URL-encode o redirect_uri para usar na URL
    encoded_redirect_uri = quote(redirect_uri, safe='')
    
    auth_url = (
        f'https://app.hubspot.com/oauth/authorize'
        f'?client_id={client_id}'
        f'&redirect_uri={encoded_redirect_uri}'
        f'&scope={scope_string}'
    )
    
    # Log para debug
    logger.info('=== OAuth Authorization Request ===')
    logger.info(f'Client ID: {client_id[:10]}...{client_id[-4:] if len(client_id) > 14 else ""}')
    logger.info(f'Redirect URI (original): {redirect_uri}')
    logger.info(f'Redirect URI (encoded): {encoded_redirect_uri}')
    logger.info(f'Auth URL: {auth_url}')
    
    return jsonify({
        'authUrl': auth_url,
        'debug': {
            'client_id_length': len(client_id),
            'redirect_uri': redirect_uri
        }
    })


@hubspot_oauth_bp.route('/callback', methods=['GET'])
def oauth_callback():
    """
    Callback OAuth do HubSpot.
    Troca o código por access token e armazena.
    """
    code = request.args.get('code')
    
    # Log todos os parâmetros recebidos
    logger.info('=== OAuth Callback Received ===')
    logger.info(f'Query params: {dict(request.args)}')
    logger.info(f'Full URL: {request.url}')
    
    if not code:
        logger.error('Código de autorização não fornecido')
        return jsonify({'error': 'Código de autorização não fornecido'}), 400
    
    try:
        # IMPORTANTE: O redirect_uri deve ser EXATAMENTE o mesmo usado na autorização
        # Usar o mesmo valor padrão do authorize
        redirect_uri = os.getenv('HUBSPOT_REDIRECT_URI', 'http://localhost:5000/api/v1/hubspot-oauth/callback')
        client_id = os.getenv('HUBSPOT_CLIENT_ID')
        client_secret = os.getenv('HUBSPOT_CLIENT_SECRET')
        
        if not client_id:
            logger.error('HUBSPOT_CLIENT_ID não configurado')
            return jsonify({'error': 'HUBSPOT_CLIENT_ID não configurado'}), 500
        
        if not client_secret:
            logger.error('HUBSPOT_CLIENT_SECRET não configurado')
            return jsonify({'error': 'HUBSPOT_CLIENT_SECRET não configurado'}), 500
        
        # Log detalhado antes de fazer a requisição
        logger.info('=== Attempting Token Exchange ===')
        logger.info(f'Client ID: {client_id[:10]}...{client_id[-4:] if len(client_id) > 14 else ""}')
        logger.info(f'Client Secret: {"*" * 10}...{client_secret[-4:] if len(client_secret) > 14 else "****"}')
        logger.info(f'Redirect URI: {redirect_uri}')
        logger.info(f'Code: {code[:20]}...{code[-10:] if len(code) > 30 else ""}')
        
        # Trocar código por access token
        token_request_data = {
            'grant_type': 'authorization_code',
            'client_id': client_id,
            'client_secret': client_secret,
            'redirect_uri': redirect_uri,  # NÃO URL-encoded aqui, deve ser o valor exato
            'code': code
        }
        
        logger.info(f'Token request data (sem secrets): grant_type={token_request_data["grant_type"]}, redirect_uri={redirect_uri}')
        
        response = requests.post(
            'https://api.hubapi.com/oauth/v1/token',
            data=token_request_data,
            headers={
                'Content-Type': 'application/x-www-form-urlencoded'
            }
        )
        
        logger.info(f'Token exchange response status: {response.status_code}')
        
        if response.status_code != 200:
            error_text = response.text
            logger.error(f'=== Token Exchange Failed ===')
            logger.error(f'Status: {response.status_code}')
            logger.error(f'Response: {error_text}')
            logger.error(f'Request redirect_uri: {redirect_uri}')
            logger.error(f'Request client_id: {client_id[:10]}...')
            
            # Tentar parsear o erro para mais detalhes
            try:
                error_json = response.json()
                logger.error(f'Error JSON: {error_json}')
            except:
                pass
            
            return jsonify({
                'error': 'Erro ao obter token de acesso', 
                'details': error_text,
                'debug': {
                    'status_code': response.status_code,
                    'redirect_uri_used': redirect_uri,
                    'client_id_length': len(client_id) if client_id else 0,
                    'code_length': len(code) if code else 0
                }
            }), 400
        
        token_data = response.json()
        access_token = token_data.get('access_token')
        refresh_token = token_data.get('refresh_token')
        expires_in = token_data.get('expires_in')
        
        logger.info('=== Token Exchange Success ===')
        logger.info(f'Access token: {access_token[:20]}...' if access_token else 'None')
        logger.info(f'Refresh token: {"Present" if refresh_token else "None"}')
        logger.info(f'Expires in: {expires_in} seconds')
        
        # Buscar informações da conta HubSpot
        account_response = requests.get(
            f'https://api.hubapi.com/oauth/v1/access-tokens/{access_token}'
        )
        
        if account_response.status_code == 200:
            account_info = account_response.json()
            hub_id = account_info.get('hub_id')
            user_email = account_info.get('user')
            
            logger.info(f'=== OAuth HubSpot Concluído ===')
            logger.info(f'Hub ID: {hub_id}')
            logger.info(f'User Email: {user_email}')
            
            # TODO: Armazenar tokens no banco de dados associados à organização
            # Organization.query.filter_by(hubspot_hub_id=hub_id).update({
            #     'hubspot_access_token': access_token,
            #     'hubspot_refresh_token': refresh_token
            # })
            
        # Redirecionar de volta para o HubSpot
        return redirect('https://app.hubspot.com/')
        
    except Exception as e:
        logger.exception(f'=== Erro no callback OAuth ===')
        logger.exception(f'Exception: {str(e)}')
        return jsonify({'error': 'Erro interno', 'message': str(e)}), 500


@hubspot_oauth_bp.route('/refresh', methods=['POST'])
def refresh_token():
    """
    Atualiza o access token usando o refresh token.
    """
    data = request.get_json()
    refresh_token = data.get('refresh_token')
    
    if not refresh_token:
        return jsonify({'error': 'Refresh token não fornecido'}), 400
    
    try:
        response = requests.post(
            'https://api.hubapi.com/oauth/v1/token',
            data={
                'grant_type': 'refresh_token',
                'client_id': os.getenv('HUBSPOT_CLIENT_ID'),
                'client_secret': os.getenv('HUBSPOT_CLIENT_SECRET'),
                'refresh_token': refresh_token
            }
        )
        
        if response.status_code != 200:
            return jsonify({'error': 'Erro ao atualizar token'}), 400
        
        return jsonify(response.json())
        
    except Exception as e:
        logger.exception(f'Erro ao atualizar token: {str(e)}')
        return jsonify({'error': 'Erro interno'}), 500


@hubspot_oauth_bp.route('/status', methods=['GET'])
def connection_status():
    """
    Retorna o status da conexão com o HubSpot.
    """
    # TODO: Buscar do banco de dados
    return jsonify({
        'connected': False,
        'hub_id': None,
        'user_email': None
    })

