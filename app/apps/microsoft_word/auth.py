"""
Microsoft Word OAuth2 Authentication.
"""

import os

MICROSOFT_CLIENT_ID = os.getenv('MICROSOFT_CLIENT_ID', '')
MICROSOFT_CLIENT_SECRET = os.getenv('MICROSOFT_CLIENT_SECRET', '')
MICROSOFT_REDIRECT_URI = os.getenv('MICROSOFT_REDIRECT_URI', '')

MICROSOFT_AUTH_URL = 'https://login.microsoftonline.com/common/oauth2/v2.0/authorize'
MICROSOFT_TOKEN_URL = 'https://login.microsoftonline.com/common/oauth2/v2.0/token'

MICROSOFT_WORD_SCOPES = ['Files.ReadWrite.All', 'offline_access']
