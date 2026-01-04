"""
OAuth Service - Handle OAuth authentication (Google, GitHub, etc.)
"""
import os
import requests
import logging
from typing import Dict, Optional, Tuple
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

# Google OAuth Configuration
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
GOOGLE_REDIRECT_URI = os.getenv('GOOGLE_REDIRECT_URI', 'http://localhost:4200/api/v1/authn/federated/callback')

# Google OAuth endpoints
GOOGLE_AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
GOOGLE_TOKEN_URL = 'https://oauth2.googleapis.com/token'
GOOGLE_USERINFO_URL = 'https://www.googleapis.com/oauth2/v2/userinfo'


class GoogleOAuthService:
    """Service for Google OAuth authentication"""

    @staticmethod
    def get_authorization_url(state: Optional[str] = None) -> str:
        """
        Generate Google OAuth authorization URL.

        Args:
            state: Optional state parameter for CSRF protection

        Returns:
            Authorization URL to redirect user to
        """
        params = {
            'client_id': GOOGLE_CLIENT_ID,
            'redirect_uri': GOOGLE_REDIRECT_URI,
            'response_type': 'code',
            'scope': 'openid email profile',
            'access_type': 'offline',
            'prompt': 'consent'
        }

        if state:
            params['state'] = state

        auth_url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"
        logger.info(f"Generated Google OAuth URL with redirect: {GOOGLE_REDIRECT_URI}")
        return auth_url

    @staticmethod
    def exchange_code_for_token(code: str) -> Optional[Dict]:
        """
        Exchange authorization code for access token.

        Args:
            code: Authorization code from Google

        Returns:
            Token response dict or None if failed
        """
        try:
            data = {
                'code': code,
                'client_id': GOOGLE_CLIENT_ID,
                'client_secret': GOOGLE_CLIENT_SECRET,
                'redirect_uri': GOOGLE_REDIRECT_URI,
                'grant_type': 'authorization_code'
            }

            response = requests.post(GOOGLE_TOKEN_URL, data=data)
            response.raise_for_status()

            token_data = response.json()
            logger.info("Successfully exchanged code for token")
            return token_data

        except Exception as e:
            logger.error(f"Failed to exchange code for token: {e}")
            return None

    @staticmethod
    def get_user_info(access_token: str) -> Optional[Dict]:
        """
        Get user information from Google.

        Args:
            access_token: Google access token

        Returns:
            User info dict with keys: id, email, verified_email, name, given_name, family_name, picture
        """
        try:
            headers = {
                'Authorization': f'Bearer {access_token}'
            }

            response = requests.get(GOOGLE_USERINFO_URL, headers=headers)
            response.raise_for_status()

            user_info = response.json()
            logger.info(f"Retrieved user info for: {user_info.get('email')}")
            return user_info

        except Exception as e:
            logger.error(f"Failed to get user info: {e}")
            return None

    @staticmethod
    def authenticate(code: str) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Complete OAuth authentication flow.

        Args:
            code: Authorization code from Google

        Returns:
            Tuple of (user_info dict, error message)
        """
        # Exchange code for token
        token_data = GoogleOAuthService.exchange_code_for_token(code)
        if not token_data:
            return None, "Failed to exchange authorization code"

        access_token = token_data.get('access_token')
        if not access_token:
            return None, "No access token in response"

        # Get user info
        user_info = GoogleOAuthService.get_user_info(access_token)
        if not user_info:
            return None, "Failed to retrieve user information"

        # Validate email is verified
        if not user_info.get('verified_email', False):
            return None, "Email is not verified with Google"

        return user_info, None


class GitHubOAuthService:
    """Service for GitHub OAuth authentication (placeholder for future implementation)"""

    @staticmethod
    def get_authorization_url(state: Optional[str] = None) -> str:
        """Generate GitHub OAuth authorization URL"""
        # TODO: Implement GitHub OAuth
        raise NotImplementedError("GitHub OAuth not yet implemented")

    @staticmethod
    def authenticate(code: str) -> Tuple[Optional[Dict], Optional[str]]:
        """Complete GitHub OAuth authentication"""
        # TODO: Implement GitHub OAuth
        raise NotImplementedError("GitHub OAuth not yet implemented")


# Convenience functions
def get_google_auth_url(state: Optional[str] = None) -> str:
    """Get Google OAuth authorization URL"""
    return GoogleOAuthService.get_authorization_url(state)


def authenticate_with_google(code: str) -> Tuple[Optional[Dict], Optional[str]]:
    """Authenticate user with Google OAuth code"""
    return GoogleOAuthService.authenticate(code)
