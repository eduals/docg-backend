from flask import Blueprint, request, jsonify, g
from app.database import db
from app.models import User, UserSession, LoginHistory, UserTwoFactorAuth, ApiKey
from app.utils.auth import require_auth, require_org
import logging
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta
import pyotp
import qrcode
import io
import base64

logger = logging.getLogger(__name__)
security_bp = Blueprint('security', __name__, url_prefix='/api/v1/users/me')


@security_bp.route('/test', methods=['GET'])
def test_endpoint():
    """Endpoint de teste para verificar se o blueprint está registrado"""
    return jsonify({'message': 'Security blueprint está funcionando!', 'status': 'ok'})


def get_current_user():
    """Helper para obter usuário atual baseado no email"""
    user_email_header = request.headers.get('X-User-Email')
    user_email_query = request.args.get('user_email')
    user_email = user_email_header or user_email_query
    
    logger.debug(
        "[get_current_user] X-User-Email=%s, user_email_query=%s, org_id=%s",
        user_email_header,
        user_email_query,
        getattr(g, 'organization_id', None),
    )
    
    if not user_email:
        return None
    
    user = User.query.filter_by(
        email=user_email,
        organization_id=g.organization_id
    ).first()
    
    return user


@security_bp.route('/sessions', methods=['GET'])
@require_auth
@require_org
def list_sessions():
    """Lista sessões ativas do usuário"""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404
    
    # Obter token atual para comparar
    current_token = request.headers.get('Authorization', '').replace('Bearer ', '')
    current_token_hash = hashlib.sha256(current_token.encode()).hexdigest() if current_token else None
    
    sessions = UserSession.query.filter_by(user_id=user.id).all()
    sessions_data = []
    for session in sessions:
        session_dict = session.to_dict()
        # Adicionar is_current baseado no token hash
        session_dict['is_current'] = (current_token_hash and 
                                      session.session_token == current_token_hash)
        sessions_data.append(session_dict)
    
    return jsonify({
        'sessions': sessions_data
    })


@security_bp.route('/sessions/<session_id>', methods=['DELETE'])
@require_auth
@require_org
def revoke_session(session_id):
    """Revoga uma sessão específica"""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404
    
    session = UserSession.query.filter_by(
        id=session_id,
        user_id=user.id
    ).first_or_404()
    
    db.session.delete(session)
    db.session.commit()
    
    return jsonify({'success': True})


@security_bp.route('/sessions', methods=['DELETE'])
@require_auth
@require_org
def revoke_all_other_sessions():
    """Revoga todas as outras sessões (exceto a atual)"""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404
    
    # Obter token da sessão atual (se disponível)
    current_token = request.headers.get('Authorization', '').replace('Bearer ', '')
    current_token_hash = hashlib.sha256(current_token.encode()).hexdigest() if current_token else None
    
    # Deletar todas as sessões exceto a atual
    if current_token_hash:
        sessions = UserSession.query.filter(
            UserSession.user_id == user.id,
            UserSession.session_token != current_token_hash
        ).all()
    else:
        # Se não temos token atual, deletar todas
        sessions = UserSession.query.filter_by(user_id=user.id).all()
    
    for session in sessions:
        db.session.delete(session)
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'revoked_count': len(sessions)
    })


@security_bp.route('/login-history', methods=['GET'])
@require_auth
@require_org
def get_login_history():
    """Retorna histórico de login do usuário (com paginação)"""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404
    
    page = request.args.get('page', 1, type=int)
    # Aceitar tanto limit quanto per_page (compatibilidade)
    limit = request.args.get('limit', type=int) or request.args.get('per_page', 20, type=int)
    
    # Limitar limit máximo
    limit = min(limit, 100)
    
    history = LoginHistory.query.filter_by(user_id=user.id)\
        .order_by(LoginHistory.created_at.desc())\
        .paginate(page=page, per_page=limit, error_out=False)
    
    return jsonify({
        'history': [entry.to_dict() for entry in history.items],
        'page': page,
        'limit': limit,
        'total': history.total
    })


@security_bp.route('/2fa', methods=['GET'])
@require_auth
@require_org
def get_2fa_status():
    """Retorna status do 2FA do usuário"""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404
    
    two_fa = UserTwoFactorAuth.query.filter_by(user_id=user.id).first()
    
    if not two_fa:
        return jsonify({
            'enabled': False,
            'backup_codes_count': 0
        })
    
    return jsonify({
        'enabled': two_fa.enabled,
        'backup_codes_count': len(two_fa.backup_codes) if two_fa.backup_codes else 0
    })


@security_bp.route('/2fa/enable', methods=['POST'])
@require_auth
@require_org
def enable_2fa():
    """Habilita 2FA - gera secret e retorna QR code"""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404
    
    # Gerar secret
    secret = pyotp.random_base32()
    
    # Criar ou atualizar registro
    two_fa = UserTwoFactorAuth.query.filter_by(user_id=user.id).first()
    if not two_fa:
        two_fa = UserTwoFactorAuth(
            user_id=user.id,
            enabled=False,
            secret=secret  # Em produção, deveria ser criptografado
        )
        db.session.add(two_fa)
    else:
        two_fa.secret = secret  # Em produção, deveria ser criptografado
        two_fa.enabled = False
    
    db.session.commit()
    
    # Gerar URL para QR code
    totp_uri = pyotp.totp.TOTP(secret).provisioning_uri(
        name=user.email,
        issuer_name='DocGen'
    )
    
    # Gerar QR code (se possível)
    qr_code_base64 = None
    try:
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(totp_uri)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        # Converter para base64
        qr_code_base64 = base64.b64encode(buffer.read()).decode()
    except ModuleNotFoundError as e:
        # Dependência opcional (Pillow) não instalada - logar e seguir sem QR code em imagem
        logger.error("PIL (Pillow) não instalada, não será possível gerar QR code em imagem: %s", e)
    
    return jsonify({
        'secret': secret,  # Em produção, não retornar o secret
        'qr_code': f'data:image/png;base64,{qr_code_base64}' if qr_code_base64 else None,
        'uri': totp_uri
    })


@security_bp.route('/2fa/verify', methods=['POST'])
@require_auth
@require_org
def verify_2fa():
    """Verifica código 2FA e habilita"""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404
    
    data = request.get_json()
    code = data.get('code')
    
    if not code:
        return jsonify({'error': 'Código é obrigatório'}), 400
    
    two_fa = UserTwoFactorAuth.query.filter_by(user_id=user.id).first()
    if not two_fa or not two_fa.secret:
        return jsonify({'error': '2FA não foi inicializado. Chame /2fa/enable primeiro'}), 400
    
    # Verificar código
    totp = pyotp.TOTP(two_fa.secret)
    if not totp.verify(code, valid_window=1):
        return jsonify({'error': 'Código inválido'}), 400
    
    # Habilitar 2FA
    two_fa.enabled = True
    
    # Gerar códigos de backup
    backup_codes = [secrets.token_hex(4) for _ in range(8)]
    two_fa.backup_codes = backup_codes  # Em produção, deveria ser criptografado
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'backup_codes': backup_codes  # Mostrar apenas uma vez
    })


@security_bp.route('/2fa/disable', methods=['POST'])
@require_auth
@require_org
def disable_2fa():
    """Desabilita 2FA"""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404
    
    data = request.get_json()
    code = data.get('code')
    
    two_fa = UserTwoFactorAuth.query.filter_by(user_id=user.id).first()
    if not two_fa or not two_fa.enabled:
        return jsonify({'error': '2FA não está habilitado'}), 400
    
    # Verificar código ou código de backup
    if code:
        totp = pyotp.TOTP(two_fa.secret)
        is_valid_code = totp.verify(code, valid_window=1)
        is_valid_backup = two_fa.backup_codes and code in two_fa.backup_codes
        
        if not (is_valid_code or is_valid_backup):
            return jsonify({'error': 'Código inválido'}), 400
        
        # Se foi código de backup, remover da lista
        if is_valid_backup:
            two_fa.backup_codes.remove(code)
    
    # Desabilitar
    two_fa.enabled = False
    two_fa.secret = None
    two_fa.backup_codes = None
    
    db.session.commit()
    
    return jsonify({'success': True})


@security_bp.route('/api-keys', methods=['GET'])
@require_auth
@require_org
def list_api_keys():
    """Lista API keys do usuário"""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404
    
    keys = ApiKey.query.filter_by(
        user_id=user.id,
        organization_id=g.organization_id
    ).all()
    
    return jsonify({
        'keys': [key.to_dict() for key in keys]
    })


@security_bp.route('/api-keys', methods=['POST'])
@require_auth
@require_org
def create_api_key():
    """Cria nova API key"""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404
    
    # Body opcional
    data = request.get_json(silent=True) or {}
    name = data.get('name', 'API Key')
    expires_in_days = data.get('expires_in_days')  # None = nunca expira
    
    # Gerar chave
    random_string = secrets.token_urlsafe(32)
    full_key = f'dg_{random_string}'
    
    # Criar hash
    key_hash = hashlib.sha256(full_key.encode()).hexdigest()
    
    # Calcular expiração
    expires_at = None
    if expires_in_days:
        expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
    
    # Criar registro
    api_key = ApiKey(
        user_id=user.id,
        organization_id=g.organization_id,
        key_prefix='dg_',
        key_hash=key_hash,
        name=name,
        expires_at=expires_at
    )
    
    db.session.add(api_key)
    db.session.commit()
    
    return jsonify({
        'key': full_key,  # Mostrar apenas uma vez
        'key_id': str(api_key.id)
    }), 201


@security_bp.route('/api-keys/<key_id>', methods=['DELETE'])
@require_auth
@require_org
def revoke_api_key(key_id):
    """Revoga uma API key"""
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Usuário não encontrado'}), 404
    
    api_key = ApiKey.query.filter_by(
        id=key_id,
        user_id=user.id,
        organization_id=g.organization_id
    ).first_or_404()
    
    db.session.delete(api_key)
    db.session.commit()
    
    return jsonify({'success': True})
