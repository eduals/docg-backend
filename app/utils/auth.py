from functools import wraps
from flask import request, jsonify, g
from app.config import Config
from app.models import User, Organization
from app.database import db
import uuid

def require_auth(f):
    """Decorator para exigir autenticação Bearer token
    Aceita token no header Authorization ou no query parameter Authorization
    Se g.token já estiver definido (por outro middleware), pula a validação
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Se já foi autenticado por outro middleware (ex: flexible_hubspot_auth), pular validação
        if hasattr(g, 'token') and g.token:
            return f(*args, **kwargs)
        
        # Tentar obter do header primeiro (prioridade)
        auth_value = request.headers.get('Authorization')
        
        # Se não encontrou no header, tentar no query parameter
        if not auth_value:
            auth_value = request.args.get('Authorization')
        
        if not auth_value:
            return jsonify({
                'error': 'Authorization header missing',
                'message': 'Bearer token é obrigatório'
            }), 401
        
        try:
            # Formato esperado: "Bearer {token}"
            token_type, token = auth_value.split(' ', 1)
            
            if token_type.lower() != 'bearer':
                return jsonify({
                    'error': 'Invalid authorization type',
                    'message': 'Tipo de autorização deve ser Bearer'
                }), 401
            
            # Validar token
            if token != Config.BACKEND_API_TOKEN:
                return jsonify({
                    'error': 'Invalid token',
                    'message': 'Token inválido'
                }), 401
            
            # Armazenar token no contexto
            g.token = token
            
        except ValueError:
            return jsonify({
                'error': 'Invalid authorization header format',
                'message': 'Formato do header Authorization inválido. Use: Bearer {token}'
            }), 401
        
        return f(*args, **kwargs)
    
    return decorated_function


def require_org(f):
    """Decorator para exigir organização no contexto (via portal_id ou organization_id)"""
    @require_auth
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Tentar obter organization_id de várias formas
        organization_id = None
        
        # 1. Path parameter (kwargs) - prioridade mais alta
        if kwargs.get('organization_id'):
            organization_id = kwargs.get('organization_id')
        
        # 2. Header X-Organization-ID
        if not organization_id:
            organization_id = request.headers.get('X-Organization-ID')
        
        # 3. Diretamente do request (query param ou body)
        if not organization_id:
            if request.args.get('organization_id'):
                organization_id = request.args.get('organization_id')
            elif request.is_json and request.get_json():
                organization_id = request.get_json().get('organization_id')
        
        # 2. Via portal_id (compatibilidade com código antigo)
        portal_id = None
        if request.args.get('portal_id'):
            portal_id = request.args.get('portal_id')
        elif request.is_json and request.get_json():
            portal_id = request.get_json().get('portal_id')
        
        if portal_id:
            # Buscar organização pelo portal_id (via connection)
            from app.utils.helpers import get_organization_id_from_portal_id
            org_id = get_organization_id_from_portal_id(portal_id)
            if org_id:
                organization_id = str(org_id)
        
        # 3. Se ainda não encontrou e tem portal_id, retornar erro (não criar automaticamente)
        # A organização deve ser criada explicitamente via migração ou endpoint
        if not organization_id and portal_id:
            return jsonify({
                'error': 'Organization not found',
                'message': f'Organização não encontrada para portal_id {portal_id}. Execute a migração de dados primeiro.'
            }), 404
        
        if not organization_id:
            return jsonify({
                'error': 'Organization not found',
                'message': 'organization_id ou portal_id é obrigatório'
            }), 400
        
        # Validar que organização existe
        try:
            org = Organization.query.filter_by(id=organization_id).first_or_404()
            g.organization_id = organization_id
            g.organization = org
        except Exception as e:
            return jsonify({
                'error': 'Invalid organization',
                'message': 'Organização não encontrada'
            }), 404
        
        return f(*args, **kwargs)
    
    return decorated_function


def require_admin(f):
    """Decorator para exigir que usuário seja admin"""
    @require_org
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Tentar obter user_id
        user_id = None
        if request.args.get('user_id'):
            user_id = request.args.get('user_id')
        elif request.is_json and request.get_json():
            user_id = request.get_json().get('user_id')
        
        # Se não tem user_id, permitir (para compatibilidade)
        if not user_id:
            return f(*args, **kwargs)
        
        # Verificar se usuário é admin
        user = User.query.filter_by(
            id=user_id,
            organization_id=g.organization_id
        ).first()
        
        if not user or not user.is_admin():
            return jsonify({
                'error': 'Permission denied',
                'message': 'Acesso negado. Apenas administradores podem realizar esta ação.'
            }), 403
        
        g.user_id = user_id
        g.user = user
        
        return f(*args, **kwargs)
    
    return decorated_function

