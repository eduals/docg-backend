"""Helper functions para registrar histórico de login"""
from flask import request
from app.database import db
from app.models import LoginHistory, User
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


def log_login_attempt(user_id, login_method, success=True, failure_reason=None):
    """
    Registra tentativa de login no histórico
    
    Args:
        user_id: UUID do usuário
        login_method: Método de login ('oauth_google', 'oauth_microsoft', 'oauth_hubspot', 'email', 'api_key')
        success: Se o login foi bem-sucedido
        failure_reason: Motivo da falha (se success=False)
    """
    try:
        ip_address = request.remote_addr or request.environ.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
        user_agent = request.headers.get('User-Agent', '')
        
        login_entry = LoginHistory(
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            login_method=login_method,
            success=success,
            failure_reason=failure_reason
        )
        
        db.session.add(login_entry)
        db.session.commit()
        
        # Limpar histórico antigo (mais de 90 dias)
        cleanup_old_login_history()
        
    except Exception as e:
        logger.error(f"Erro ao registrar login: {str(e)}")
        db.session.rollback()


def cleanup_old_login_history():
    """Remove histórico de login com mais de 90 dias (conforme LGPD/GDPR)"""
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=90)
        old_entries = LoginHistory.query.filter(LoginHistory.created_at < cutoff_date).all()
        
        for entry in old_entries:
            db.session.delete(entry)
        
        if old_entries:
            db.session.commit()
            logger.info(f"Removidos {len(old_entries)} registros de login antigos")
    except Exception as e:
        logger.error(f"Erro ao limpar histórico de login: {str(e)}")
        db.session.rollback()


def log_successful_login(user_email, organization_id, login_method):
    """
    Helper para registrar login bem-sucedido
    
    Args:
        user_email: Email do usuário
        organization_id: ID da organização
        login_method: Método de login
    """
    try:
        user = User.query.filter_by(
            email=user_email,
            organization_id=organization_id
        ).first()
        
        if user:
            log_login_attempt(user.id, login_method, success=True)
    except Exception as e:
        logger.error(f"Erro ao registrar login bem-sucedido: {str(e)}")


def log_failed_login(user_email, organization_id, login_method, failure_reason):
    """
    Helper para registrar login falho
    
    Args:
        user_email: Email do usuário (pode ser None se não encontrado)
        organization_id: ID da organização
        login_method: Método de login
        failure_reason: Motivo da falha
    """
    try:
        user = None
        if user_email and organization_id:
            user = User.query.filter_by(
                email=user_email,
                organization_id=organization_id
            ).first()
        
        if user:
            log_login_attempt(user.id, login_method, success=False, failure_reason=failure_reason)
        else:
            # Registrar tentativa mesmo sem usuário encontrado (para segurança)
            # Usar um user_id temporário ou None - mas LoginHistory requer user_id
            # Por enquanto, vamos apenas logar sem criar entrada se não houver usuário
            logger.warning(f"Tentativa de login falha para usuário não encontrado: {user_email}")
    except Exception as e:
        logger.error(f"Erro ao registrar login falho: {str(e)}")
