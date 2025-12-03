from flask import Blueprint, request, jsonify, redirect
from app.database import db
from app.models import GoogleOAuthToken, GoogleDriveConfig, Organization, User
from app.auth import require_auth
from app.utils.auth import require_org
from app.utils.hubspot_auth import flexible_hubspot_auth
from flask import g
from app.config import Config
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import os
import json
import re
import uuid
import logging
import base64
import hashlib
import secrets

logger = logging.getLogger(__name__)
bp = Blueprint('google_oauth', __name__, url_prefix='/api/v1/google-oauth')

# Scopes necessários para Google Drive, Docs e RISC
SCOPES = [
    'https://www.googleapis.com/auth/userinfo.profile',  # Necessário para RISC
    'https://www.googleapis.com/auth/userinfo.email',    # Alternativa ao profile
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/documents.readonly',
    'https://www.googleapis.com/auth/drive.file'
]

# Armazenamento temporário para code_verifier (PKCE)
# Usando banco de dados para persistir entre reinicializações do servidor
_PKCE_TTL = 600  # 10 minutos

def _normalize_scopes(scopes):
    """
    Normaliza scopes do Google OAuth, convertendo formatos curtos para URLs completas.
    
    Args:
        scopes: Lista de scopes (strings)
        
    Returns:
        Lista de scopes normalizados
    """
    scope_mapping = {
        'email': 'https://www.googleapis.com/auth/userinfo.email',
        'profile': 'https://www.googleapis.com/auth/userinfo.profile',
        'openid': 'openid'  # openid já é um scope válido
    }
    
    normalized = []
    for scope in scopes:
        normalized.append(scope_mapping.get(scope, scope))
    
    # Remover duplicatas mantendo a ordem
    seen = set()
    result = []
    for scope in normalized:
        if scope not in seen:
            seen.add(scope)
            result.append(scope)
    
    return result

def _generate_code_verifier():
    """Gera um code_verifier para PKCE (43-128 caracteres, URL-safe)"""
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')

def _generate_code_challenge(verifier):
    """Gera code_challenge a partir do code_verifier usando SHA256"""
    challenge = hashlib.sha256(verifier.encode('utf-8')).digest()
    return base64.urlsafe_b64encode(challenge).decode('utf-8').rstrip('=')

def _store_pkce_verifier(state, verifier):
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
        expires_at=expires_at
    )
    db.session.add(pkce_entry)
    db.session.commit()
    
    # Limpar entradas expiradas (background cleanup)
    _cleanup_expired_pkce()

def _get_pkce_verifier(state):
    """Recupera code_verifier associado ao state do banco de dados"""
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
    
    # Recuperar verifier e remover (one-time use)
    verifier = entry.code_verifier
    db.session.delete(entry)
    db.session.commit()
    
    return verifier

def _cleanup_expired_pkce():
    """Remove entradas expiradas do banco de dados"""
    from app.models import PKCEVerifier
    
    try:
        expired = PKCEVerifier.query.filter(PKCEVerifier.expires_at < datetime.utcnow()).all()
        for entry in expired:
            db.session.delete(entry)
        db.session.commit()
    except Exception as e:
        logger.warning(f"Erro ao limpar PKCE expirados: {str(e)}")
        db.session.rollback()

@bp.route('/status', methods=['GET'])
@require_org
def get_oauth_status():
    """Verificar status de conexão"""
    try:
        organization_id = g.organization_id
        
        token = GoogleOAuthToken.query.filter_by(organization_id=organization_id).first()
        
        if not token:
            return jsonify({
                'success': True,
                'connected': False,
                'email': None,
                'scopes': []
            }), 200
        
        # Tentar carregar credenciais e renovar se necessário
        creds = None
        is_connected = False
        email = None
        
        try:
            creds_data = json.loads(token.access_token)
            creds = Credentials.from_authorized_user_info(creds_data, SCOPES)
            
            # Se token expirou, tentar renovar usando refresh_token
            if creds.expired or token.is_expired():
                if creds.refresh_token:
                    try:
                        creds.refresh(Request())
                        # Atualizar no banco após renovação bem-sucedida
                        token.access_token = creds.to_json()
                        token.token_expiry = creds.expiry
                        db.session.commit()
                        is_connected = True
                    except Exception as refresh_error:
                        # Se renovação falhar, conexão está desconectada
                        logger.warning(f"Error refreshing token: {refresh_error}")
                        is_connected = False
                else:
                    # Não há refresh_token para renovar
                    is_connected = False
            else:
                # Token ainda válido
                is_connected = True
            
            # Tentar obter email do usuário se token válido
            if is_connected:
                try:
                    service = build('oauth2', 'v2', credentials=creds)
                    user_info = service.userinfo().get().execute()
                    email = user_info.get('email')
                except Exception:
                    pass
                    
        except Exception as e:
            logger.error(f"Error getting credentials: {e}")
            is_connected = False
        
        return jsonify({
            'success': True,
            'connected': is_connected,
            'email': email,
            'scopes': token.scope.split(',') if token.scope else []
        }), 200
        
    except Exception as e:
        logger.error(f"Error in get_oauth_status: {e}")
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500


@bp.route('/authorize', methods=['GET'])
@flexible_hubspot_auth
def authorize():
    """
    Iniciar fluxo OAuth com PKCE (Proof Key for Code Exchange).
    
    Para primeiro acesso: não requer organization_id - será criado automaticamente no callback.
    Para acessos subsequentes: pode enviar organization_id opcionalmente.
    """
    try:
        # organization_id é opcional - buscar de query params ou body, mas não exigir
        organization_id = request.args.get('organization_id')
        if not organization_id and request.is_json:
            organization_id = (request.get_json() or {}).get('organization_id')
        
        redirect_uri = request.args.get('redirect_uri')
        
        if not redirect_uri:
            return jsonify({
                'error': 'redirect_uri is required'
            }), 400
        
        # Configurar OAuth flow
        client_id = os.getenv('GOOGLE_CLIENT_ID', '').strip()
        client_secret = os.getenv('GOOGLE_CLIENT_SECRET', '').strip()
        
        if not client_id or not client_secret:
            logger.error(f"Google OAuth credentials not configured - client_id: {bool(client_id)}, client_secret: {bool(client_secret)}")
            return jsonify({
                'error': 'Google OAuth credentials not configured'
            }), 500
        
        # Gerar PKCE code_verifier e code_challenge
        code_verifier = _generate_code_verifier()
        code_challenge = _generate_code_challenge(code_verifier)
        
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [redirect_uri]
                }
            },
            scopes=SCOPES,
            redirect_uri=redirect_uri
        )
        
        # Gerar URL de autorização com PKCE
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent',
            code_challenge=code_challenge,
            code_challenge_method='S256'
        )
        
        # Armazenar code_verifier associado ao state (no banco de dados para persistir entre reinicializações)
        _store_pkce_verifier(state, code_verifier)
        
        # Incluir organization_id no state apenas se existir
        # Se não existir, o callback criará automaticamente
        if organization_id:
            state_with_org = f"{state}:{organization_id}"
        else:
            state_with_org = state
        
        return jsonify({
            'success': True,
            'authorization_url': authorization_url,
            'state': state_with_org
        }), 200
        
    except Exception as e:
        logger.error(f"Erro ao gerar URL de autorização: {str(e)}", exc_info=True)
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500


@bp.route('/callback', methods=['GET', 'POST'])
def callback():
    """
    Callback do OAuth.
    Endpoint público - não requer autenticação pois é chamado pelo Google via redirecionamento.
    Suporta tanto GET (redirecionamento do Google) quanto POST (chamada manual).
    Se for o primeiro login (não existe organização), cria Organization + User admin automaticamente.
    """
    try:
        # Suportar tanto GET (query params) quanto POST (body)
        if request.method == 'GET':
            code = request.args.get('code')
            state = request.args.get('state')
            redirect_uri = request.args.get('redirect_uri')
            organization_id = request.args.get('organization_id')
            scope_param = request.args.get('scope')  # Extrair scopes do callback
            
            # Extrair organization_id do state se estiver no formato "state:organization_id"
            if state and ':' in state:
                state_parts = state.split(':', 1)
                state = state_parts[0]
                if not organization_id:
                    organization_id = state_parts[1]
        else:
            data = request.get_json() or {}
            code = data.get('code')
            state = data.get('state')
            redirect_uri = data.get('redirect_uri')
            organization_id = data.get('organization_id')
            scope_param = data.get('scope')  # Extrair scopes do callback
            
            # Extrair organization_id do state se estiver no formato "state:organization_id"
            if state and ':' in state:
                state_parts = state.split(':', 1)
                state = state_parts[0]
                if not organization_id:
                    organization_id = state_parts[1]
        
        if not code:
            return jsonify({
                'error': 'code is required'
            }), 400
        
        # Se não tem redirect_uri, usar o padrão do .env
        if not redirect_uri:
            redirect_uri = os.getenv('GOOGLE_REDIRECT_URI', 'http://localhost:5000/api/v1/google-oauth/callback')
        
        # Configurar OAuth flow
        client_id = os.getenv('GOOGLE_CLIENT_ID', '').strip()
        client_secret = os.getenv('GOOGLE_CLIENT_SECRET', '').strip()
        
        if not client_id or not client_secret:
            logger.error(f"Callback: Google OAuth credentials not configured - client_id: {bool(client_id)}, client_secret: {bool(client_secret)}")
            return jsonify({
                'error': 'Google OAuth credentials not configured'
            }), 500
        
        # Recuperar code_verifier do PKCE usando o state original
        code_verifier = None
        if state:
            code_verifier = _get_pkce_verifier(state)
            if not code_verifier:
                logger.warning(f"Code verifier não encontrado ou expirado para state: {state}")
        
        # Determinar scopes a usar
        # Se scope_param estiver disponível, usar os scopes retornados pelo Google
        # Caso contrário, usar os scopes padrão
        if scope_param:
            # Usar scopes retornados pelo Google e normalizar
            scopes_to_use = _normalize_scopes(scope_param.split())
            logger.info(f"Usando scopes normalizados do callback: {scopes_to_use}")
        else:
            # Usar scopes padrão
            scopes_to_use = SCOPES
            logger.info(f"Usando scopes padrão: {scopes_to_use}")
        
        # Criar flow com scopes corretos desde o início
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [redirect_uri]
                }
            },
            scopes=scopes_to_use,  # Usar scopes do callback ou padrão
            redirect_uri=redirect_uri
        )
        
        # Trocar código por tokens com PKCE
        # O flow já foi criado com os scopes corretos, então não deve haver scope mismatch
        if code_verifier:
            # Usar PKCE se code_verifier disponível
            flow.fetch_token(code=code, code_verifier=code_verifier)
        else:
            # Fallback sem PKCE (para compatibilidade com tokens antigos)
            logger.warning("PKCE code_verifier não disponível, usando fluxo sem PKCE")
            flow.fetch_token(code=code)
        
        credentials = flow.credentials
        
        # Obter informações do usuário Google
        service = build('oauth2', 'v2', credentials=credentials)
        user_info = service.userinfo().get().execute()
        google_email = user_info.get('email')
        google_name = user_info.get('name', '')
        google_user_id = user_info.get('id')
        
        # Se não tem organization_id, criar organização e usuário admin
        if not organization_id:
            # Verificar se já existe organização para este email (via User)
            existing_user = User.query.filter_by(email=google_email).first()
            
            if existing_user:
                # Usuário já existe, usar organização dele
                organization_id = str(existing_user.organization_id)
                org = Organization.query.filter_by(id=organization_id).first()
            else:
                # Criar nova organização
                org_name = google_name or google_email.split('@')[0]
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
                    billing_email=google_email,
                    trial_expires_at=trial_expires_at
                )
                db.session.add(org)
                db.session.flush()  # Para obter o ID
                
                # Criar usuário admin
                # hubspot_user_id será NULL inicialmente - será preenchido quando instalar app no HubSpot
                admin_user = User(
                    organization_id=org.id,
                    email=google_email,
                    name=google_name,
                    role='admin',
                    google_user_id=google_user_id,
                    hubspot_user_id=None  # Será preenchido depois quando instalar app no HubSpot
                )
                db.session.add(admin_user)
                organization_id = str(org.id)
        else:
            # Organização já existe, verificar se usuário existe
            org = Organization.query.filter_by(id=organization_id).first_or_404()
            existing_user = User.query.filter_by(
                organization_id=organization_id,
                email=google_email
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
                    email=google_email,
                    name=google_name,
                    role=user_role,
                    google_user_id=google_user_id
                )
                db.session.add(new_user)
        
        # Validar que organization_id existe
        if not organization_id:
            return jsonify({
                'error': 'organization_id is required to save OAuth token'
            }), 400
        
        # Garantir que organization_id seja UUID
        try:
            organization_id = uuid.UUID(organization_id) if isinstance(organization_id, str) else organization_id
        except (ValueError, AttributeError):
            return jsonify({
                'error': 'Invalid organization_id format'
            }), 400
        
        # Salvar ou atualizar tokens no banco usando organization_id
        token = GoogleOAuthToken.query.filter_by(organization_id=organization_id).first()
        
        if token:
            token.access_token = credentials.to_json()
            token.refresh_token = credentials.refresh_token
            token.token_expiry = credentials.expiry
            token.scope = ','.join(credentials.scopes) if credentials.scopes else None
            token.updated_at = datetime.utcnow()
        else:
            token = GoogleOAuthToken(
                organization_id=organization_id,
                access_token=credentials.to_json(),
                refresh_token=credentials.refresh_token,
                token_expiry=credentials.expiry,
                scope=','.join(credentials.scopes) if credentials.scopes else None
            )
            db.session.add(token)
        
        db.session.commit()
        
        # Se for GET (redirecionamento do Google), retornar HTML de sucesso
        if request.method == 'GET':
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
                        color: #4CAF50;
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
                    <p>Conta Google conectada com sucesso.</p>
                    <p><strong>Organization ID:</strong> {organization_id}</p>
                    <p><strong>Email:</strong> {google_email}</p>
                    <p style="margin-top: 20px; font-size: 14px; color: #999;">Você pode fechar esta janela.</p>
                </div>
            </body>
            </html>
            """, 200
        
        # Se for POST, retornar JSON
        return jsonify({
            'success': True,
            'message': 'Google account connected successfully',
            'organization_id': organization_id,
            'user': {
                'email': google_email,
                'name': google_name
            }
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro no callback OAuth: {str(e)}", exc_info=True)
        
        # Se for GET, retornar HTML de erro
        if request.method == 'GET':
            error_msg = str(e).replace('<', '&lt;').replace('>', '&gt;')
            return f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Erro na Autorização</title>
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
                        max-width: 500px;
                    }}
                    h1 {{
                        color: #f44336;
                        margin-bottom: 20px;
                    }}
                    p {{
                        color: #666;
                        margin-bottom: 10px;
                    }}
                    .error {{
                        background: #ffebee;
                        padding: 15px;
                        border-radius: 4px;
                        margin-top: 20px;
                        color: #c62828;
                        font-size: 14px;
                        text-align: left;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>✗ Erro na Autorização</h1>
                    <p>Ocorreu um erro ao processar a autorização.</p>
                    <div class="error">
                        <strong>Erro:</strong><br>
                        {error_msg}
                    </div>
                    <p style="margin-top: 20px; font-size: 14px; color: #999;">Por favor, tente novamente.</p>
                </div>
            </body>
            </html>
            """, 500
        
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500

@bp.route('/disconnect', methods=['POST'])
@require_org
def disconnect():
    """Desconectar conta Google"""
    try:
        organization_id = g.organization_id
        
        token = GoogleOAuthToken.query.filter_by(organization_id=organization_id).first()
        
        if token:
            db.session.delete(token)
            db.session.commit()
        
        # Também remover configuração do Google Drive se existir
        config = GoogleDriveConfig.query.filter_by(organization_id=organization_id).first()
        if config:
            db.session.delete(config)
            db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Google account disconnected successfully'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500

