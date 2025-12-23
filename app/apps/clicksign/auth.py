"""
ClickSign Authentication Configuration.

ClickSign usa API Key para autenticação.
"""

import os
from typing import Dict, Any

# Configuração
CLICKSIGN_API_KEY = os.getenv('CLICKSIGN_API_KEY', '')
CLICKSIGN_SANDBOX = os.getenv('CLICKSIGN_SANDBOX', 'false').lower() == 'true'

# URLs
CLICKSIGN_BASE_URL = 'https://sandbox.clicksign.com/api/v1' if CLICKSIGN_SANDBOX else 'https://app.clicksign.com/api/v1'


def get_api_headers(api_key: str = None) -> Dict[str, str]:
    """
    Retorna headers para chamadas à API.

    Args:
        api_key: API key (usa env var se não fornecido)

    Returns:
        Dict com headers
    """
    return {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }


def get_api_params(api_key: str = None) -> Dict[str, str]:
    """
    Retorna query params para chamadas à API.

    Args:
        api_key: API key (usa env var se não fornecido)

    Returns:
        Dict com params incluindo access_token
    """
    key = api_key or CLICKSIGN_API_KEY
    return {
        'access_token': key,
    }
