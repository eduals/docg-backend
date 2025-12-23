"""
AuditEvent Model - Audit trail append-only.

Feature 6: Auditoria Append-Only
- Trail imutável para compliance
- Rastreamento de todas as ações em execuções
"""
import uuid
from datetime import datetime
from app.database import db
from sqlalchemy.dialects.postgresql import UUID, JSONB


class AuditEvent(db.Model):
    """
    Eventos de auditoria append-only (nunca UPDATE/DELETE).

    Registra todas as ações executadas em workflows:
    - execution.started, execution.completed, execution.canceled
    - document.generated, document.sent
    - signature.requested, signature.signed
    - etc.
    """
    __tablename__ = 'audit_events'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Organização (para compliance multi-tenant)
    organization_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey('organizations.id', ondelete='CASCADE'),
        nullable=False
    )

    # Timestamp
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Ator (quem fez a ação)
    actor_type = db.Column(db.String(20), nullable=False)  # user, system, webhook
    actor_id = db.Column(db.String(255), nullable=True)    # user_id, "temporal", "stripe"

    # Ação
    action = db.Column(db.String(100), nullable=False)     # execution.started, document.generated

    # Alvo da ação
    target_type = db.Column(db.String(50), nullable=False)  # execution, document, signature
    target_id = db.Column(UUID(as_uuid=True), nullable=False)

    # Metadados adicionais (renamed from 'metadata' - SQLAlchemy reserved word)
    event_metadata = db.Column(JSONB, nullable=True)

    # Relacionamento
    organization = db.relationship('Organization')

    # Índices
    __table_args__ = (
        db.Index('idx_audit_events_org_target', 'organization_id', 'target_type', 'target_id'),
        db.Index('idx_audit_events_timestamp', 'timestamp'),
        db.Index('idx_audit_events_action', 'action'),
    )

    def to_dict(self):
        """Converte para dicionário"""
        return {
            'id': str(self.id),
            'organization_id': str(self.organization_id),
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'actor_type': self.actor_type,
            'actor_id': self.actor_id,
            'action': self.action,
            'target_type': self.target_type,
            'target_id': str(self.target_id),
            'metadata': self.event_metadata  # API mantém nome 'metadata'
        }

    @classmethod
    def create(
        cls,
        organization_id: str,
        action: str,
        target_type: str,
        target_id: str,
        actor_type: str = 'system',
        actor_id: str = None,
        metadata: dict = None
    ):
        """
        Factory method para criar evento de auditoria.

        Args:
            organization_id: UUID da organização
            action: Ação executada (ex: 'execution.started')
            target_type: Tipo do alvo (ex: 'execution')
            target_id: UUID do alvo
            actor_type: Tipo do ator ('user', 'system', 'webhook')
            actor_id: ID do ator (opcional)
            metadata: Dados extras (opcional)

        Returns:
            Nova instância de AuditEvent
        """
        return cls(
            organization_id=organization_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            actor_type=actor_type,
            actor_id=actor_id,
            event_metadata=metadata  # Use event_metadata internally
        )

    @classmethod
    def get_for_execution(cls, target_id: str, cursor: str = None, limit: int = 50):
        """
        Busca eventos de auditoria para uma execução.

        Args:
            target_id: UUID da execução
            cursor: UUID do último evento (para paginação)
            limit: Máximo de resultados

        Returns:
            Lista de AuditEvent ordenados por timestamp
        """
        query = cls.query.filter_by(
            target_type='execution',
            target_id=target_id
        )

        if cursor:
            cursor_event = cls.query.get(cursor)
            if cursor_event:
                query = query.filter(cls.timestamp > cursor_event.timestamp)

        limit = min(limit, 100)

        return query.order_by(cls.timestamp).limit(limit).all()


# === Ações de auditoria (constantes) ===

class AuditAction:
    """Ações de auditoria disponíveis"""
    # Execuções
    EXECUTION_STARTED = 'execution.started'
    EXECUTION_CANCELED = 'execution.canceled'
    EXECUTION_RETRIED = 'execution.retried'
    EXECUTION_RESUMED = 'execution.resumed'
    EXECUTION_COMPLETED = 'execution.completed'
    EXECUTION_FAILED = 'execution.failed'

    # Documentos
    DOCUMENT_GENERATED = 'document.generated'
    DOCUMENT_SAVED = 'document.saved'
    DOCUMENT_SENT = 'document.sent'

    # Assinaturas
    SIGNATURE_REQUESTED = 'signature.requested'
    SIGNATURE_SIGNED = 'signature.signed'
    SIGNATURE_DECLINED = 'signature.declined'
    SIGNATURE_EXPIRED = 'signature.expired'

    # Templates
    TEMPLATE_VERSION_UPDATED = 'template.version_updated'
