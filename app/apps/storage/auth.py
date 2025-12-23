"""Storage Authentication."""

import os

DO_SPACES_KEY = os.getenv('DO_SPACES_KEY', '')
DO_SPACES_SECRET = os.getenv('DO_SPACES_SECRET', '')
DO_SPACES_BUCKET = os.getenv('DO_SPACES_BUCKET', '')
DO_SPACES_REGION = os.getenv('DO_SPACES_REGION', 'nyc3')
