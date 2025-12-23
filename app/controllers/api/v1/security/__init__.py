"""
Security Controllers.

Controllers para gerenciamento de segurança (sessões, 2FA, API keys).
"""

from .sessions import list_sessions, revoke_session, revoke_all_other_sessions
from .login_history import get_login_history
from .two_factor import get_2fa_status, enable_2fa, verify_2fa, disable_2fa
from .api_keys import list_api_keys, create_api_key, revoke_api_key

# Aliases para compatibilidade
enable_two_factor = enable_2fa
verify_two_factor = verify_2fa
disable_two_factor = disable_2fa

__all__ = [
    # Sessions
    'list_sessions',
    'revoke_session',
    'revoke_all_other_sessions',
    # Login history
    'get_login_history',
    # 2FA
    'get_2fa_status',
    'enable_2fa',
    'verify_2fa',
    'disable_2fa',
    'enable_two_factor',
    'verify_two_factor',
    'disable_two_factor',
    # API Keys
    'list_api_keys',
    'create_api_key',
    'revoke_api_key',
]
