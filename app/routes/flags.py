"""
Flags API - Endpoints para feature flags e configurações.
Compatível com ActivePieces UI.
"""

from flask import Blueprint, jsonify

bp = Blueprint('flags', __name__)


@bp.route('/api/v1/flags', methods=['GET'])
def get_flags():
    """
    Retorna feature flags para a UI.

    Returns:
        JSON com flags ativadas/desativadas
    """
    # Flags padrão para compatibilidade com ActivePieces UI
    flags = {
        # Authentication & Setup
        'USER_CREATED': True,  # Permite sign-in (se False, redireciona para sign-up)
        'EDITION': 'CLOUD',  # COMMUNITY, CLOUD, ENTERPRISE
        'EMAIL_AUTH_ENABLED': True,  # Habilita autenticação por email/senha

        # Platform Features
        'SHOW_PLATFORM_DEMO': False,
        'SHOW_BILLING': True,
        'SHOW_COMMUNITY': False,
        'SHOW_DOCS': True,
        'SHOW_TEMPLATES': True,
        'SHOW_AI_FEATURES': True,
        'SHOW_ANALYTICS': True,
        'EMBED_ENABLED': False,
        'COPILOT_ENABLED': False,
        'PIECES_SYNC_ENABLED': True,
        'SHOW_ACTIVITY_LOG': True,
        'SHOW_FLOW_RUN_DETAILS': True,
        'SHOW_CONNECTIONS': True,
        'SIGNING_KEY_REQUIRED': False,
        'CLOUD_AUTH_ENABLED': False,
        'PROJECT_MEMBERS_ENABLED': True,
        'GIT_SYNC_ENABLED': False,
        'CUSTOM_DOMAINS_ENABLED': False,
        'SHOW_POWERED_BY': False,
        'TELEMETRY_ENABLED': False,
        'SHOW_REWARDS': False,
        'SHOW_BLOG_GUIDE': False,
        'MANAGED_AUTH_ENABLED': False,
        'THIRD_PARTY_AUTH_PROVIDERS_ENABLED': False,
        'SHOW_PLATFORM_ADMIN': True,

        # Branding
        'THEME': {
            'websiteName': 'PipeHub',
            'logos': {
                'fullLogoUrl': 'https://activepieces.com/logo-full.svg',
                'favIconUrl': 'https://activepieces.com/favicon.ico',
                'logoIconUrl': 'https://activepieces.com/logo-icon.svg',
            },
            'colors': {
                'primary': {
                    'default': '#6366F1',
                    'dark': '#4F46E5',
                    'light': '#818CF8',
                },
            },
        },
    }

    return jsonify(flags), 200
