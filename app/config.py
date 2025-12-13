import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

def normalize_database_url(url):
    """Normaliza a URL do banco para usar o driver psycopg2"""
    if url.startswith('postgres://'):
        return url.replace('postgres://', 'postgresql+psycopg2://', 1)
    elif url.startswith('postgresql://') and '+psycopg2' not in url:
        return url.replace('postgresql://', 'postgresql+psycopg2://', 1)
    return url

class Config:
    # Database
    _db_url = os.getenv('DATABASE_URL', 'postgresql://user:password@localhost:5432/clicksign_db')
    SQLALCHEMY_DATABASE_URI = normalize_database_url(_db_url)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Security
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    BACKEND_API_TOKEN = os.getenv('BACKEND_API_TOKEN', 'dev-backend-token-change-in-production')
    
    # Flask
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
    DEBUG = os.getenv('FLASK_ENV') == 'development'
    
    # Trial settings
    TRIAL_DAYS = 20
    
    # Google OAuth
    GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', '')
    GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET', '')
    GOOGLE_REDIRECT_URI = os.getenv('GOOGLE_REDIRECT_URI', '')
    
    # Google Service Account (para RISC)
    # Opção 1: Variáveis de ambiente individuais
    GOOGLE_SERVICE_ACCOUNT_TYPE = os.getenv('GOOGLE_SERVICE_ACCOUNT_TYPE', '')
    GOOGLE_SERVICE_ACCOUNT_PROJECT_ID = os.getenv('GOOGLE_SERVICE_ACCOUNT_PROJECT_ID', '')
    GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY_ID = os.getenv('GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY_ID', '')
    GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY = os.getenv('GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY', '')
    GOOGLE_SERVICE_ACCOUNT_CLIENT_EMAIL = os.getenv('GOOGLE_SERVICE_ACCOUNT_CLIENT_EMAIL', '')
    GOOGLE_SERVICE_ACCOUNT_CLIENT_ID = os.getenv('GOOGLE_SERVICE_ACCOUNT_CLIENT_ID', '')
    GOOGLE_SERVICE_ACCOUNT_AUTH_URI = os.getenv('GOOGLE_SERVICE_ACCOUNT_AUTH_URI', 'https://accounts.google.com/o/oauth2/auth')
    GOOGLE_SERVICE_ACCOUNT_TOKEN_URI = os.getenv('GOOGLE_SERVICE_ACCOUNT_TOKEN_URI', 'https://oauth2.googleapis.com/token')
    GOOGLE_SERVICE_ACCOUNT_AUTH_PROVIDER_X509_CERT_URL = os.getenv('GOOGLE_SERVICE_ACCOUNT_AUTH_PROVIDER_X509_CERT_URL', 'https://www.googleapis.com/oauth2/v1/certs')
    GOOGLE_SERVICE_ACCOUNT_CLIENT_X509_CERT_URL = os.getenv('GOOGLE_SERVICE_ACCOUNT_CLIENT_X509_CERT_URL', '')
    GOOGLE_SERVICE_ACCOUNT_UNIVERSE_DOMAIN = os.getenv('GOOGLE_SERVICE_ACCOUNT_UNIVERSE_DOMAIN', 'googleapis.com')
    
    # Opção 2: Caminho para arquivo JSON (alternativa)
    GOOGLE_SERVICE_ACCOUNT_KEY_PATH = os.getenv('GOOGLE_SERVICE_ACCOUNT_KEY_PATH', '')
    GOOGLE_APPLICATION_CREDENTIALS = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', '')
    
    # Stripe
    STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY', '')
    STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY', '')
    STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET', '')
    FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:5173')

