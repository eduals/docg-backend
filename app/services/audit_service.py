"""
AuditService - Helper para registrar eventos de auditoria.

Feature 6: Auditoria Append-Only
"""
from typing import Optional, Dict
from app.models.audit_event import AuditEvent
from app.database import db


class AuditService:
    """
    Service para registrar eventos de auditoria.

    Uso:
        AuditService.log(
            organization_id='uuid',
            action='execution.started',
            target_type='execution',
            target_id='uuid',
            actor_type='user',
            actor_id='user-uuid'
        )
    """

    @staticmethod
    def log(
        organization_id: str,
        action: str,
        target_type: str,
        target_id: str,
        actor_type: str = 'system',
        actor_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> AuditEvent:
        """
        Registra evento de auditoria.

        Args:
            organization_id: UUID da organização
            action: Ação executada
            target_type: Tipo do alvo
            target_id: UUID do alvo
            actor_type: Tipo do ator
            actor_id: ID do ator
            metadata: Dados extras

        Returns:
            AuditEvent criado
        """
        event = AuditEvent.create(
            organization_id=organization_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            actor_type=actor_type,
            actor_id=actor_id,
            metadata=metadata
        )

        db.session.add(event)

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            # Log to stdout as fallback
            print(f"[AuditService] Failed to persist audit event: {e}")
            print(f"  action={action}, target_type={target_type}, target_id={target_id}")

        return event

    @staticmethod
    def log_execution_started(execution_id: str, organization_id: str, actor_id: str = None):
        """Registra início de execução"""
        return AuditService.log(
            organization_id=organization_id,
            action='execution.started',
            target_type='execution',
            target_id=execution_id,
            actor_type='user' if actor_id else 'system',
            actor_id=actor_id
        )

    @staticmethod
    def log_execution_completed(execution_id: str, organization_id: str):
        """Registra conclusão de execução"""
        return AuditService.log(
            organization_id=organization_id,
            action='execution.completed',
            target_type='execution',
            target_id=execution_id,
            actor_type='system'
        )

    @staticmethod
    def log_execution_failed(execution_id: str, organization_id: str, error: str = None):
        """Registra falha de execução"""
        return AuditService.log(
            organization_id=organization_id,
            action='execution.failed',
            target_type='execution',
            target_id=execution_id,
            actor_type='system',
            metadata={'error': error} if error else None
        )

    @staticmethod
    def log_execution_canceled(execution_id: str, organization_id: str, actor_id: str, reason: str = None):
        """Registra cancelamento de execução"""
        return AuditService.log(
            organization_id=organization_id,
            action='execution.canceled',
            target_type='execution',
            target_id=execution_id,
            actor_type='user',
            actor_id=actor_id,
            metadata={'reason': reason} if reason else None
        )

    @staticmethod
    def log_document_generated(execution_id: str, organization_id: str, document_id: str):
        """Registra geração de documento"""
        return AuditService.log(
            organization_id=organization_id,
            action='document.generated',
            target_type='execution',
            target_id=execution_id,
            actor_type='system',
            metadata={'document_id': document_id}
        )

    @staticmethod
    def log_signature_requested(execution_id: str, organization_id: str, envelope_id: str, signers: list):
        """Registra solicitação de assinatura"""
        return AuditService.log(
            organization_id=organization_id,
            action='signature.requested',
            target_type='execution',
            target_id=execution_id,
            actor_type='system',
            metadata={'envelope_id': envelope_id, 'signers': signers}
        )
