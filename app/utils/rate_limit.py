"""
Rate Limiting Configuration
Protects endpoints from abuse and brute-force attacks
"""
import os
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask import request
import logging

logger = logging.getLogger(__name__)

# Environment check
IS_DEVELOPMENT = os.getenv('FLASK_ENV') == 'development'

# Redis configuration for rate limiting
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')


def get_identifier():
    """
    Get unique identifier for rate limiting.
    Uses IP address, but can be extended to use user ID for authenticated requests.
    """
    # For authenticated requests, could use user ID from JWT
    # For now, use IP address
    identifier = get_remote_address()

    # Log rate limit checks
    logger.debug(f"Rate limit check for: {identifier}")

    return identifier


# Initialize limiter
limiter = Limiter(
    key_func=get_identifier,
    storage_uri=REDIS_URL,
    storage_options={
        "socket_connect_timeout": 30,
        "socket_timeout": 30
    },
    strategy="fixed-window",
    default_limits=["200 per hour"]  # Default global limit
)


# Custom decorators for different rate limits

def rate_limit_auth_strict():
    """
    Strict rate limit for authentication endpoints.
    Prevents brute force attacks.

    Limits:
    - Development: 100/min, 1000/hour
    - Production: 5/min, 20/hour
    """
    if IS_DEVELOPMENT:
        return limiter.limit("100 per minute;1000 per hour")
    return limiter.limit("5 per minute;20 per hour")


def rate_limit_auth_medium():
    """
    Medium rate limit for auth-related endpoints like OTP.

    Limits:
    - Development: 50/min, 500/hour
    - Production: 3/min, 10/hour
    """
    if IS_DEVELOPMENT:
        return limiter.limit("50 per minute;500 per hour")
    return limiter.limit("3 per minute;10 per hour")


def rate_limit_signup():
    """
    Rate limit for sign-up endpoint.

    Limits:
    - Development: 100/hour, 1000/day
    - Production: 3/hour, 10/day
    """
    if IS_DEVELOPMENT:
        return limiter.limit("100 per hour;1000 per day")
    return limiter.limit("3 per hour;10 per day")


def rate_limit_oauth():
    """
    Rate limit for OAuth endpoints.

    Limits:
    - Development: 100/min, 1000/hour
    - Production: 10/min, 50/hour
    """
    if IS_DEVELOPMENT:
        return limiter.limit("100 per minute;1000 per hour")
    return limiter.limit("10 per minute;50 per hour")


def rate_limit_api():
    """
    Standard rate limit for API endpoints.

    Limits:
    - 60 per minute
    - 1000 per hour
    """
    return limiter.limit("60 per minute;1000 per hour")


# Error handler for rate limit exceeded
@limiter.request_filter
def rate_limit_exempt():
    """
    Exempt certain requests from rate limiting.
    For example, health checks or internal services.
    """
    # Exempt health check endpoint
    if request.path == '/health':
        return True

    # Exempt if coming from internal network (optional)
    # if request.remote_addr == '127.0.0.1':
    #     return True

    return False
