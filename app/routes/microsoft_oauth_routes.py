"""
Rotas para OAuth do Microsoft Graph API.
Similar ao Google OAuth, mas para Microsoft 365/OneDrive.
"""
from flask import Blueprint, request, jsonify, redirect, g
from app.database import db
from app.models import DataSourceConnection, Organization, User
from app.utils.auth import require_auth, require_org
from app.utils.hubspot_auth import flexible_hubspot_auth
from app.utils.encryption import encrypt_credentials, decrypt_credentials
from app.config import Config
from datetime import datetime, timedelta
from urllib.parse import urlencode
from typing import Dict, Any, Optional
import os
import json
import uuid
import logging
import secrets
import base64
import hashlib
import requests
import re

logger = logging.getLogger(__name__)
microsoft_oauth_bp = Blueprint('microsoft_oauth', __name__, url_prefix='/api/v1/microsoft/oauth')

# Microsoft OAuth endpoints
MICROSOFT_AUTHORIZATION_ENDPOINT = 'https://login.microsoftonline.com/common/oauth2/v2.0/authorize'
MICROSOFT_TOKEN_ENDPOINT = 'https://login.microsoftonline.com/common/oauth2/v2.0/token'

# Scopes necessários para Microsoft Graph API
SCOPES = [
    'Files.ReadWrite.All',  # Ler e escrever arquivos no OneDrive/SharePoint
    'Mail.Send',             # Enviar emails (para Outlook)
    'User.Read',             # Ler perfil do usuário
    'offline_access'         # Refresh token
]

# Armazenamento temporário para PKCE (usar mesmo modelo do Google)
_PKCE_TTL = 600  # 10 minutos

def _generate_code_verifier():
    """Gera um code_verifier para PKCE (43-128 caracteres, URL-safe)"""
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')

def _generate_code_challenge(verifier):
    """Gera code_challenge a partir do code_verifier usando SHA256"""
    challenge = hashlib.sha256(verifier.encode('utf-8')).digest()
    return base64.urlsafe_b64encode(challenge).decode('utf-8').rstrip('=')

def _store_pkce_verifier(state, verifier, frontend_redirect_uri=None):
    """Armazena code_verifier temporariamente associado ao state no banco de dados"""
    from app.models import PKCEVerifier
    
    expires_at = datetime.utcnow() + timedelta(seconds=_PKCE_TTL)
    
    # Remover entrada existente se houver (one-time use)
    existing = PKCEVerifier.query.filter_by(state=state).first()
    if existing:
        db.session.delete(existing)
    
    # Criar nova entrada
    pkce_entry = PKCEVerifier(
        state=state,
        code_verifier=verifier,
        frontend_redirect_uri=frontend_redirect_uri,
        expires_at=expires_at
    )
    db.session.add(pkce_entry)
    db.session.commit()
    
    return pkce_entry

def _get_pkce_verifier(state):
    """Recupera code_verifier do banco de dados"""
    from app.models import PKCEVerifier
    
    pkce_entry = PKCEVerifier.query.filter_by(state=state).first()
    if not pkce_entry:
        return None
    
    # Verificar se expirou
    if pkce_entry.expires_at < datetime.utcnow():
        db.session.delete(pkce_entry)
        db.session.commit()
        return None
    
    # Remover após uso (one-time use)
    verifier = pkce_entry.code_verifier
    db.session.delete(pkce_entry)
    db.session.commit()
    
    return verifier

def _get_frontend_redirect_uri(state):
    """Recupera frontend_redirect_uri associado ao state do banco de dados
    IMPORTANTE: Esta função NÃO remove a entrada do banco (será removida quando _get_pkce_verifier for chamado)
    """
    from app.models import PKCEVerifier
    
    if not state:
        return None
    
    entry = PKCEVerifier.query.filter_by(state=state).first()
    
    if not entry:
        return None
    
    # Verificar se expirou
    if datetime.utcnow() > entry.expires_at:
        db.session.delete(entry)
        db.session.commit()
        return None
    
    # Recuperar frontend_redirect_uri (não remover entry aqui, será removido junto com verifier)
    return entry.frontend_redirect_uri


@microsoft_oauth_bp.route('/authorize', methods=['GET'])
@flexible_hubspot_auth
def authorize():
    """
    Inicia o fluxo OAuth do Microsoft.
    Similar ao Google OAuth - não requer organization_id para primeiro acesso.
    
    Query params:
    - frontend_redirect_uri: URI para redirecionar após autenticação
    - organization_id: ID da organização (opcional, será criado automaticamente se não existir)
    """
    frontend_redirect_uri = request.args.get('frontend_redirect_uri')
    # organization_id é opcional - buscar de query params ou g.organization_id, mas não exigir
    organization_id = request.args.get('organization_id')
    if not organization_id and hasattr(g, 'organization_id'):
        organization_id = g.organization_id
    
    # Obter credenciais do Microsoft do config
    client_id = os.getenv('MICROSOFT_CLIENT_ID')
    client_secret = os.getenv('MICROSOFT_CLIENT_SECRET')
    
    if not client_id or not client_secret:
        return jsonify({
            'error': 'Microsoft OAuth não configurado. Configure MICROSOFT_CLIENT_ID e MICROSOFT_CLIENT_SECRET'
        }), 500
    
    # Gerar state e PKCE
    state = secrets.token_urlsafe(32)
    code_verifier = _generate_code_verifier()
    code_challenge = _generate_code_challenge(code_verifier)
    
    # Armazenar code_verifier
    _store_pkce_verifier(state, code_verifier, frontend_redirect_uri)
    
    # Construir URL de autorização
    redirect_uri = os.getenv('MICROSOFT_REDIRECT_URI', f'{request.url_root.rstrip("/")}/api/v1/microsoft/oauth/callback')
    scope_string = ' '.join(SCOPES)
    
    params = {
        'client_id': client_id,
        'response_type': 'code',
        'redirect_uri': redirect_uri,
        'response_mode': 'query',
        'scope': scope_string,
        'state': state,
        'code_challenge': code_challenge,
        'code_challenge_method': 'S256',
    }
    
    authorization_url = f"{MICROSOFT_AUTHORIZATION_ENDPOINT}?{urlencode(params)}"
    
    return jsonify({
        'success': True,
        'authorization_url': authorization_url,
        'state': state
    })


@microsoft_oauth_bp.route('/callback', methods=['GET', 'POST'])
def callback():
    """
    Callback do OAuth do Microsoft.
    Recebe o código de autorização e troca por access token.
    Se for o primeiro login (não existe organização), cria Organization + User admin automaticamente.
    """
    try:
        # Suportar tanto GET (query params) quanto POST (body)
        if request.method == 'GET':
            code = request.args.get('code')
            state = request.args.get('state')
            error = request.args.get('error')
        else:
            data = request.get_json(silent=True) or {}
            code = data.get('code')
            state = data.get('state')
            error = data.get('error')
        
        if error:
            logger.error(f'Erro no callback do Microsoft OAuth: {error}')
            if request.method == 'GET':
                return redirect(f"/login?error={error}")
            return jsonify({'error': f'OAuth error: {error}'}), 400
        
        if not code or not state:
            if request.method == 'GET':
                return redirect("/login?error=missing_code_or_state")
            return jsonify({'error': 'code e state são obrigatórios'}), 400
        
        # Recuperar code_verifier e frontend_redirect_uri
        frontend_redirect_uri = _get_frontend_redirect_uri(state)
        code_verifier = _get_pkce_verifier(state)
        if not code_verifier:
            if request.method == 'GET':
                return redirect("/login?error=invalid_state")
            return jsonify({'error': 'State inválido ou expirado'}), 400
        
        # Obter credenciais
        client_id = os.getenv('MICROSOFT_CLIENT_ID')
        client_secret = os.getenv('MICROSOFT_CLIENT_SECRET')
        redirect_uri = os.getenv('MICROSOFT_REDIRECT_URI', f'{request.url_root.rstrip("/")}/api/v1/microsoft/oauth/callback')
        
        if not client_id or not client_secret:
            logger.error("Microsoft OAuth credentials not configured")
            if request.method == 'GET':
                return redirect("/login?error=oauth_not_configured")
            return jsonify({'error': 'Microsoft OAuth credentials not configured'}), 500
        
        # Trocar código por token
        token_data = {
            'client_id': client_id,
            'client_secret': client_secret,
            'code': code,
            'redirect_uri': redirect_uri,
            'grant_type': 'authorization_code',
            'code_verifier': code_verifier,
        }
        
        response = requests.post(MICROSOFT_TOKEN_ENDPOINT, data=token_data)
        response.raise_for_status()
        token_response = response.json()
        
        access_token = token_response.get('access_token')
        refresh_token = token_response.get('refresh_token')
        expires_in = token_response.get('expires_in', 3600)
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        
        # Obter informações do usuário
        user_info_response = requests.get(
            'https://graph.microsoft.com/v1.0/me',
            headers={'Authorization': f'Bearer {access_token}'}
        )
        user_info_response.raise_for_status()
        user_info = user_info_response.json()
        
        microsoft_email = user_info.get('mail') or user_info.get('userPrincipalName')
        microsoft_name = user_info.get('displayName', '')
        microsoft_user_id = user_info.get('id')
        
        # Se não tem organization_id, criar organização e usuário admin
        organization_id = None
        if not organization_id:
            # Verificar se já existe organização para este email (via User)
            existing_user = User.query.filter_by(email=microsoft_email).first()
            
            if existing_user:
                # Usuário já existe, usar organização dele
                organization_id = str(existing_user.organization_id)
                org = Organization.query.filter_by(id=organization_id).first()
            else:
                # Criar nova organização
                from app.config import Config
                import re
                
                org_name = microsoft_name or microsoft_email.split('@')[0]
                slug_base = re.sub(r'[^a-z0-9]+', '-', org_name.lower()).strip('-')
                slug = slug_base
                counter = 1
                
                while Organization.query.filter_by(slug=slug).first():
                    slug = f"{slug_base}-{counter}"
                    counter += 1
                
                # Configurar trial (20 dias por padrão)
                trial_expires_at = datetime.utcnow() + timedelta(days=Config.TRIAL_DAYS)
                
                org = Organization(
                    name=org_name,
                    slug=slug,
                    plan='free',
                    billing_email=microsoft_email,
                    trial_expires_at=trial_expires_at
                )
                db.session.add(org)
                db.session.flush()  # Para obter o ID
                
                # Criar usuário admin
                admin_user = User(
                    organization_id=org.id,
                    email=microsoft_email,
                    name=microsoft_name,
                    role='admin',
                    google_user_id=microsoft_user_id,  # Reutilizar campo google_user_id temporariamente
                    hubspot_user_id=None
                )
                db.session.add(admin_user)
                organization_id = str(org.id)
        else:
            # Organização já existe, verificar se usuário existe
            org = Organization.query.filter_by(id=organization_id).first_or_404()
            existing_user = User.query.filter_by(
                organization_id=organization_id,
                email=microsoft_email
            ).first()
            
            if not existing_user:
                # Criar usuário (primeiro usuário vira admin se não houver admin)
                admin_count = User.query.filter_by(
                    organization_id=organization_id,
                    role='admin'
                ).count()
                
                user_role = 'admin' if admin_count == 0 else 'user'
                
                new_user = User(
                    organization_id=organization_id,
                    email=microsoft_email,
                    name=microsoft_name,
                    role=user_role,
                    google_user_id=microsoft_user_id  # Reutilizar campo google_user_id temporariamente
                )
                db.session.add(new_user)
        
        # Validar que organization_id existe
        if not organization_id:
            if request.method == 'GET':
                return redirect("/login?error=organization_creation_failed")
            return jsonify({'error': 'organization_id is required'}), 400
        
        # Garantir que organization_id seja UUID
        try:
            organization_id_uuid = uuid.UUID(organization_id) if isinstance(organization_id, str) else organization_id
        except (ValueError, AttributeError):
            if request.method == 'GET':
                return redirect("/login?error=invalid_organization_id")
            return jsonify({'error': 'Invalid organization_id format'}), 400
        
        # Criar ou atualizar conexão Microsoft
        connection = DataSourceConnection.query.filter_by(
            organization_id=organization_id_uuid,
            source_type='microsoft'
        ).first()
        
        # Criptografar credenciais
        credentials_data = {
            'access_token': access_token,
            'refresh_token': refresh_token,
            'expires_at': expires_at.isoformat(),
            'user_email': microsoft_email,
            'user_name': microsoft_name,
        }
        
        encrypted_credentials = encrypt_credentials(credentials_data)
        
        if connection:
            connection.credentials = {'encrypted': encrypted_credentials}
            connection.status = 'active'
            connection.updated_at = datetime.utcnow()
        else:
            connection = DataSourceConnection(
                organization_id=organization_id_uuid,
                source_type='microsoft',
                name=f'Microsoft ({microsoft_name or "User"})',
                credentials={'encrypted': encrypted_credentials},
                status='active'
            )
            db.session.add(connection)
        
        db.session.commit()
        
        # Registrar login bem-sucedido
        try:
            from app.utils.login_logger import log_successful_login
            log_successful_login(microsoft_email, organization_id_uuid, 'oauth_microsoft')
        except Exception as e:
            logger.error(f"Erro ao registrar login: {str(e)}")
        
        # Se for GET (redirecionamento do Microsoft), redirecionar para frontend
        if request.method == 'GET':
            if frontend_redirect_uri:
                params = {
                    'organization_id': str(organization_id),
                    'email': microsoft_email,
                    'name': microsoft_name
                }
                redirect_url = f"{frontend_redirect_uri}?{urlencode(params)}"
                logger.info(f"Redirecionando para frontend: {redirect_url}")
                return redirect(redirect_url)
            
            # Caso contrário, mostrar página de sucesso
            return f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Autorização Concluída</title>
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        height: 100vh;
                        margin: 0;
                        background: #f5f5f5;
                    }}
                    .container {{
                        background: white;
                        padding: 40px;
                        border-radius: 8px;
                        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                        text-align: center;
                        max-width: 400px;
                    }}
                    h1 {{
                        color: #0078d4;
                        margin-bottom: 20px;
                    }}
                    p {{
                        color: #666;
                        margin-bottom: 10px;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>✓ Autorização Concluída!</h1>
                    <p>Conta Microsoft conectada com sucesso.</p>
                    <p><strong>Organization ID:</strong> {str(organization_id)}</p>
                    <p><strong>Email:</strong> {microsoft_email}</p>
                    <p style="margin-top: 20px; font-size: 14px; color: #999;">Você pode fechar esta janela.</p>
                </div>
            </body>
            </html>
            """, 200
        
        # Se for POST, retornar JSON
        return jsonify({
            'success': True,
            'message': 'Microsoft account connected successfully',
            'organization_id': str(organization_id),
            'user': {
                'email': microsoft_email,
                'name': microsoft_name
            }
        })
        
    except requests.exceptions.RequestException as e:
        logger.exception(f'Erro ao trocar código por token: {str(e)}')
        if request.method == 'GET':
            return redirect(f"/login?error={str(e)}")
        return jsonify({'error': f'Erro ao autenticar: {str(e)}'}), 500
    except Exception as e:
        logger.exception(f'Erro inesperado no callback: {str(e)}')
        db.session.rollback()
        if request.method == 'GET':
            return redirect(f"/login?error={str(e)}")
        return jsonify({'error': str(e)}), 500


@microsoft_oauth_bp.route('/status', methods=['GET'])
@flexible_hubspot_auth
@require_org
def status():
    """
    Verifica status da conexão Microsoft.
    """
    organization_id = g.organization_id
    
    connection = DataSourceConnection.query.filter_by(
        organization_id=organization_id,
        source_type='microsoft',
        status='active'
    ).first()
    
    if not connection:
        return jsonify({
            'success': True,
            'connected': False
        })
    
    # Verificar se token está válido
    try:
        credentials = connection.get_decrypted_credentials()
        access_token = credentials.get('access_token')
        expires_at_str = credentials.get('expires_at')
        
        if not access_token:
            return jsonify({
                'success': True,
                'connected': False
            })
        
        # Verificar se expirou
        if expires_at_str:
            expires_at = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
            if expires_at < datetime.utcnow():
                # Tentar refresh
                refreshed = _refresh_microsoft_token(connection)
                if not refreshed:
                    return jsonify({
                        'success': True,
                        'connected': False,
                        'message': 'Token expirado e não foi possível renovar'
                    })
        
        # Verificar token fazendo request simples
        test_response = requests.get(
            'https://graph.microsoft.com/v1.0/me',
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=5
        )
        
        if test_response.ok:
            user_info = test_response.json()
            return jsonify({
                'success': True,
                'connected': True,
                'email': user_info.get('mail') or user_info.get('userPrincipalName'),
                'name': user_info.get('displayName'),
                'scopes': SCOPES
            })
        else:
            return jsonify({
                'success': True,
                'connected': False,
                'message': 'Token inválido'
            })
            
    except Exception as e:
        logger.exception(f'Erro ao verificar status: {str(e)}')
        return jsonify({
            'success': True,
            'connected': False,
            'message': str(e)
        })


def get_microsoft_credentials(organization_id: str) -> Optional[Dict[str, Any]]:
    """
    Obtém credenciais Microsoft para uma organização.
    
    Args:
        organization_id: ID da organização
        
    Returns:
        Dict com credenciais (access_token, refresh_token, expires_at, user_email) ou None
    """
    from app.models import DataSourceConnection
    
    connection = DataSourceConnection.query.filter_by(
        organization_id=organization_id,
        source_type='microsoft',
        status='active'
    ).first()
    
    if not connection:
        return None
    
    try:
        credentials = connection.get_decrypted_credentials()
        access_token = credentials.get('access_token')
        
        if not access_token:
            return None
        
        # Verificar se token expirou e renovar se necessário
        expires_at_str = credentials.get('expires_at')
        if expires_at_str:
            expires_at = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
            if expires_at < datetime.utcnow():
                # Tentar refresh
                refreshed = _refresh_microsoft_token(connection)
                if not refreshed:
                    return None
                credentials = connection.get_decrypted_credentials()
                access_token = credentials.get('access_token')
        
        return {
            'access_token': access_token,
            'refresh_token': credentials.get('refresh_token'),
            'expires_at': credentials.get('expires_at'),
            'user_email': credentials.get('user_email'),
        }
    except Exception as e:
        logger.exception(f'Erro ao obter credenciais Microsoft: {str(e)}')
        return None


def _refresh_microsoft_token(connection: DataSourceConnection) -> bool:
    """
    Atualiza o access token usando refresh token.
    
    Returns:
        True se atualizado com sucesso, False caso contrário
    """
    try:
        from flask import current_app
        credentials = connection.get_decrypted_credentials()
        refresh_token = credentials.get('refresh_token')
        
        if not refresh_token:
            return False
        
        client_id = os.getenv('MICROSOFT_CLIENT_ID')
        client_secret = os.getenv('MICROSOFT_CLIENT_SECRET')
        # Usar URL base do config ou padrão
        api_base_url = current_app.config.get('API_BASE_URL', 'http://localhost:5000')
        redirect_uri = os.getenv('MICROSOFT_REDIRECT_URI', f'{api_base_url.rstrip("/")}/api/v1/microsoft/oauth/callback')
        
        token_data = {
            'client_id': client_id,
            'client_secret': client_secret,
            'refresh_token': refresh_token,
            'grant_type': 'refresh_token',
            'redirect_uri': redirect_uri,
        }
        
        response = requests.post(MICROSOFT_TOKEN_ENDPOINT, data=token_data)
        response.raise_for_status()
        token_response = response.json()
        
        access_token = token_response.get('access_token')
        new_refresh_token = token_response.get('refresh_token', refresh_token)  # Manter o antigo se não vier novo
        expires_in = token_response.get('expires_in', 3600)
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        
        # Atualizar credenciais
        credentials['access_token'] = access_token
        credentials['refresh_token'] = new_refresh_token
        credentials['expires_at'] = expires_at.isoformat()
        
        encrypted_credentials = encrypt_credentials(credentials)
        connection.credentials = {'encrypted': encrypted_credentials}
        connection.updated_at = datetime.utcnow()
        
        db.session.commit()
        return True
        
    except Exception as e:
        logger.exception(f'Erro ao atualizar token: {str(e)}')
        db.session.rollback()
        return False

