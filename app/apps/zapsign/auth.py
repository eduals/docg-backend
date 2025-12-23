"""
ZapSign Authentication Configuration.
"""

import os

ZAPSIGN_API_KEY = os.getenv('ZAPSIGN_API_KEY', '')
ZAPSIGN_BASE_URL = 'https://api.zapsign.com.br/api/v1'


def get_api_headers(api_key: str = None) -> dict:
    """Retorna headers para API"""
    key = api_key or ZAPSIGN_API_KEY
    return {
        'Authorization': f'Bearer {key}',
        'Content-Type': 'application/json',
    }
