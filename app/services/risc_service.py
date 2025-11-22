"""
Serviço para processamento de eventos RISC (Cross-Account Protection).
Processa notificações de eventos de segurança do Google e toma ações apropriadas.
"""
import logging
from typing import Dict, Optional
from datetime import datetime
from app.database import db
from app.models import GoogleOAuthToken, User
# Importar RiscEvent - está definido no models.py principal
# Usar import direto do módulo models.py para evitar circular
import importlib
import sys

def _get_risc_event():
    """Importa RiscEvent do models.py principal"""
    models_main = sys.modules.get('app.models')
    if models_main and hasattr(models_main, 'RiscEvent'):
        return models_main.RiscEvent
    # Fallback: importar diretamente
    from app import models
    return models.RiscEvent

RiscEvent = _get_risc_event()
from app.utils.jwt_validator import validate_risc_token

logger = logging.getLogger(__name__)


class RiscService:
    """Serviço para processar eventos RISC"""
    
    @staticmethod
    def process_security_event(token: str) -> Dict:
        """
        Processa um evento de segurança RISC.
        
        Args:
            token: Token JWT do evento RISC
            
        Returns:
            Dict com resultado do processamento
        """
        try:
            # Validar token
            payload = validate_risc_token(token)
            
            # Extrair informações do evento
            event_type = payload.get('events', [{}])[0].get('https://schemas.openid.net/secevent/risc/event-type')
            subject = payload.get('sub')  # Google user ID
            issuer = payload.get('iss')
            issued_at = datetime.utcfromtimestamp(payload.get('iat', 0))
            
            logger.info(f"Processando evento RISC: {event_type} para usuário {subject}")
            
            # Registrar evento no banco
            risc_event = RiscEvent(
                google_user_id=subject,
                event_type=event_type,
                token_payload=payload,
                processed=False
            )
            db.session.add(risc_event)
            db.session.flush()
            
            # Processar evento baseado no tipo
            action_taken = None
            affected_users = []
            
            if event_type == 'https://schemas.openid.net/secevent/risc/event-type/account-disabled':
                action_taken = RiscService._handle_account_disabled(subject)
                affected_users = RiscService._find_users_by_google_id(subject)
                
            elif event_type == 'https://schemas.openid.net/secevent/risc/event-type/account-enabled':
                action_taken = RiscService._handle_account_enabled(subject)
                affected_users = RiscService._find_users_by_google_id(subject)
                
            elif event_type == 'https://schemas.openid.net/secevent/risc/event-type/account-credential-change-required':
                action_taken = RiscService._handle_credential_change_required(subject)
                affected_users = RiscService._find_users_by_google_id(subject)
                
            elif event_type == 'https://schemas.openid.net/secevent/risc/event-type/sessions-revoked':
                action_taken = RiscService._handle_sessions_revoked(subject)
                affected_users = RiscService._find_users_by_google_id(subject)
                
            else:
                logger.warning(f"Tipo de evento RISC não reconhecido: {event_type}")
                action_taken = "event_logged"
            
            # Atualizar evento como processado
            risc_event.processed = True
            risc_event.action_taken = action_taken
            risc_event.processed_at = datetime.utcnow()
            
            db.session.commit()
            
            return {
                'success': True,
                'event_id': str(risc_event.id),
                'event_type': event_type,
                'action_taken': action_taken,
                'affected_users_count': len(affected_users)
            }
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Erro ao processar evento RISC: {str(e)}", exc_info=True)
            raise
    
    @staticmethod
    def _find_users_by_google_id(google_user_id: str) -> list:
        """Encontra usuários do sistema associados a um Google user ID"""
        return User.query.filter_by(google_user_id=google_user_id).all()
    
    @staticmethod
    def _handle_account_disabled(google_user_id: str) -> str:
        """
        Processa evento de conta desabilitada.
        Ação: Invalidar tokens OAuth do usuário.
        """
        users = RiscService._find_users_by_google_id(google_user_id)
        
        for user in users:
            # Invalidar tokens OAuth associados
            # Usar organization_id como identificador
            token = GoogleOAuthToken.query.filter_by(
                organization_id=user.organization_id
            ).first()
            
            if token:
                # Marcar token como inválido (deletar ou marcar flag)
                db.session.delete(token)
                logger.info(f"Token OAuth invalidado para organização {user.organization_id}")
        
        return "tokens_invalidated"
    
    @staticmethod
    def _handle_account_enabled(google_user_id: str) -> str:
        """
        Processa evento de conta reabilitada.
        Ação: Registrar evento (usuário precisará reconectar manualmente).
        """
        logger.info(f"Conta Google reabilitada: {google_user_id}")
        return "event_logged"
    
    @staticmethod
    def _handle_credential_change_required(google_user_id: str) -> str:
        """
        Processa evento de mudança de credenciais necessária.
        Ação: Invalidar tokens e forçar reconexão.
        """
        users = RiscService._find_users_by_google_id(google_user_id)
        
        for user in users:
            tokens = GoogleOAuthToken.query.filter_by(
                portal_id=str(user.organization_id)
            ).all()
            
            for token in tokens:
                db.session.delete(token)
                logger.info(f"Token OAuth invalidado (credential change) para organização {user.organization_id}")
        
        return "tokens_invalidated_credential_change"
    
    @staticmethod
    def _handle_sessions_revoked(google_user_id: str) -> str:
        """
        Processa evento de sessões revogadas.
        Ação: Invalidar tokens OAuth.
        """
        users = RiscService._find_users_by_google_id(google_user_id)
        
        for user in users:
            tokens = GoogleOAuthToken.query.filter_by(
                portal_id=str(user.organization_id)
            ).all()
            
            for token in tokens:
                db.session.delete(token)
                logger.info(f"Token OAuth invalidado (sessions revoked) para organização {user.organization_id}")
        
        return "tokens_invalidated_sessions_revoked"

