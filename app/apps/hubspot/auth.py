"""
HubSpot OAuth2 Authentication Configuration.

Este módulo contém configurações e helpers para autenticação OAuth2
com o HubSpot. Reutiliza lógica existente de hubspot_oauth_routes.py.
"""

import os
from typing import Dict, Any, Optional

# OAuth2 Configuration
HUBSPOT_CLIENT_ID = os.getenv('HUBSPOT_CLIENT_ID', '')
HUBSPOT_CLIENT_SECRET = os.getenv('HUBSPOT_CLIENT_SECRET', '')
HUBSPOT_REDIRECT_URI = os.getenv('HUBSPOT_REDIRECT_URI', '')

HUBSPOT_AUTH_URL = 'https://app.hubspot.com/oauth/authorize'
HUBSPOT_TOKEN_URL = 'https://api.hubapi.com/oauth/v1/token'

# Scopes necessários
HUBSPOT_SCOPES = [
    'crm.objects.contacts.read',
    'crm.objects.contacts.write',
    'crm.objects.deals.read',
    'crm.objects.deals.write',
    'crm.objects.companies.read',
    'crm.objects.companies.write',
    'crm.schemas.contacts.read',
    'crm.schemas.deals.read',
    'crm.schemas.companies.read',
    'files',
]


def get_authorization_url(state: str = None, redirect_uri: str = None) -> str:
    """
    Gera URL de autorização OAuth2.

    Args:
        state: State parameter para CSRF protection
        redirect_uri: Override do redirect URI

    Returns:
        URL completa para redirecionar o usuário
    """
    from urllib.parse import urlencode

    params = {
        'client_id': HUBSPOT_CLIENT_ID,
        'redirect_uri': redirect_uri or HUBSPOT_REDIRECT_URI,
        'scope': ' '.join(HUBSPOT_SCOPES),
    }

    if state:
        params['state'] = state

    return f"{HUBSPOT_AUTH_URL}?{urlencode(params)}"


async def exchange_code_for_tokens(code: str, redirect_uri: str = None) -> Dict[str, Any]:
    """
    Troca authorization code por access/refresh tokens.

    Args:
        code: Authorization code recebido do callback
        redirect_uri: Redirect URI usado na autorização

    Returns:
        Dict com access_token, refresh_token, expires_in
    """
    import httpx

    async with httpx.AsyncClient() as client:
        response = await client.post(
            HUBSPOT_TOKEN_URL,
            data={
                'grant_type': 'authorization_code',
                'client_id': HUBSPOT_CLIENT_ID,
                'client_secret': HUBSPOT_CLIENT_SECRET,
                'redirect_uri': redirect_uri or HUBSPOT_REDIRECT_URI,
                'code': code,
            },
        )
        response.raise_for_status()
        return response.json()


async def refresh_access_token(refresh_token: str) -> Dict[str, Any]:
    """
    Renova access token usando refresh token.

    Args:
        refresh_token: Refresh token válido

    Returns:
        Dict com novo access_token, refresh_token, expires_in
    """
    import httpx

    async with httpx.AsyncClient() as client:
        response = await client.post(
            HUBSPOT_TOKEN_URL,
            data={
                'grant_type': 'refresh_token',
                'client_id': HUBSPOT_CLIENT_ID,
                'client_secret': HUBSPOT_CLIENT_SECRET,
                'refresh_token': refresh_token,
            },
        )
        response.raise_for_status()
        return response.json()


def get_portal_id_from_token(access_token: str) -> Optional[str]:
    """
    Obtém portal ID (hub ID) a partir do access token.

    Args:
        access_token: Token de acesso válido

    Returns:
        Portal ID ou None
    """
    import requests

    try:
        response = requests.get(
            'https://api.hubapi.com/oauth/v1/access-tokens/' + access_token
        )
        if response.status_code == 200:
            data = response.json()
            return str(data.get('hub_id'))
    except Exception:
        pass
    return None
