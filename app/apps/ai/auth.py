"""AI Authentication - API Keys for various providers."""

import os

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
GOOGLE_AI_API_KEY = os.getenv('GOOGLE_AI_API_KEY', '')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')
