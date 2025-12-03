"""
Rotas de OAuth do HubSpot.
Gerencia autenticação e autorização com o HubSpot.
"""

from flask import Blueprint, request, jsonify, redirect
import requests
import os
import logging

logger = logging.getLogger(__name__)

hubspot_oauth_bp = Blueprint('hubspot_oauth', __name__, url_prefix='/api/v1/hubspot-oauth')


@hubspot_oauth_bp.route('/authorize', methods=['GET'])
def authorize():
    """
    Inicia o fluxo de autorização OAuth do HubSpot.
    Retorna a URL para o usuário autorizar o app.
    """
    client_id = os.getenv('HUBSPOT_CLIENT_ID')
    redirect_uri = os.getenv('HUBSPOT_REDIRECT_URI', 'https://hs-service.pipehub.co/api/v1/hubspot-oauth/callback')
    
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
    from urllib.parse import quote
    encoded_redirect_uri = quote(redirect_uri, safe='')
    
    auth_url = (
        f'https://app.hubspot.com/oauth/authorize'
        f'?client_id={client_id}'
        f'&redirect_uri={encoded_redirect_uri}'
        f'&scope={scope_string}'
    )
    
    return jsonify({
        'authUrl': auth_url
    })


@hubspot_oauth_bp.route('/callback', methods=['GET'])
def oauth_callback():
    """
    Callback OAuth do HubSpot.
    Troca o código por access token e armazena.
    """
    code = request.args.get('code')
    
    if not code:
        logger.error('Código de autorização não fornecido')
        return jsonify({'error': 'Código de autorização não fornecido'}), 400
    
    try:
        # IMPORTANTE: O redirect_uri deve ser EXATAMENTE o mesmo usado na autorização
        # Usar o mesmo valor padrão do authorize
        redirect_uri = os.getenv('HUBSPOT_REDIRECT_URI', 'https://hs-service.pipehub.co/api/v1/hubspot-oauth/callback')
        
        # Trocar código por access token
        response = requests.post(
            'https://api.hubapi.com/oauth/v1/token',
            data={
                'grant_type': 'authorization_code',
                'client_id': os.getenv('HUBSPOT_CLIENT_ID'),
                'client_secret': os.getenv('HUBSPOT_CLIENT_SECRET'),
                'redirect_uri': redirect_uri,  # NÃO URL-encoded aqui, deve ser o valor exato
                'code': code
            }
        )
        
        if response.status_code != 200:
            logger.error(f'Erro ao trocar código por token: {response.text}')
            return jsonify({'error': 'Erro ao obter token de acesso', 'details': response.text}), 400
        
        token_data = response.json()
        access_token = token_data.get('access_token')
        refresh_token = token_data.get('refresh_token')
        expires_in = token_data.get('expires_in')
        
        # Buscar informações da conta HubSpot
        account_response = requests.get(
            f'https://api.hubapi.com/oauth/v1/access-tokens/{access_token}'
        )
        
        if account_response.status_code == 200:
            account_info = account_response.json()
            hub_id = account_info.get('hub_id')
            user_email = account_info.get('user')
            
            logger.info(f'OAuth HubSpot concluído para hub_id: {hub_id}, user: {user_email}')
            
            # TODO: Armazenar tokens no banco de dados associados à organização
            # Organization.query.filter_by(hubspot_hub_id=hub_id).update({
            #     'hubspot_access_token': access_token,
            #     'hubspot_refresh_token': refresh_token
            # })
            
        # Redirecionar de volta para o HubSpot
        return redirect('https://app.hubspot.com/')
        
    except Exception as e:
        logger.exception(f'Erro no callback OAuth: {str(e)}')
        return jsonify({'error': 'Erro interno'}), 500


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

