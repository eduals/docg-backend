"""
WorkflowDatastore - Armazenamento persistente key-value para workflows.

Permite que actions armazenem dados entre execuções.
Escopo pode ser por organização, workflow ou execução.
"""

import uuid
from datetime import datetime
from app.database import db
from sqlalchemy.dialects.postgresql import UUID, JSONB


class WorkflowDatastore(db.Model):
    """
    Armazenamento persistente key-value.

    Escopos suportados:
    - organization: Compartilhado por toda organização
    - workflow: Específico para um workflow
    - execution: Específico para uma execução

    Exemplo de uso:
        # Salvar valor global da organização
        await datastore.set('last_sync', datetime.now().isoformat())

        # Obter valor
        last_sync = await datastore.get('last_sync')
    """
    __tablename__ = 'workflow_datastores'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey('organizations.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )

    # Escopo do dado
    scope = db.Column(
        db.String(50),
        nullable=False,
        default='organization'
    )  # 'organization', 'workflow', 'execution'

    # ID do escopo (workflow_id ou execution_id)
    scope_id = db.Column(UUID(as_uuid=True), nullable=True, index=True)

    # Key-value
    key = db.Column(db.String(255), nullable=False)
    value = db.Column(JSONB, nullable=True)

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)  # TTL opcional

    # Índices
    __table_args__ = (
        db.UniqueConstraint(
            'organization_id', 'scope', 'scope_id', 'key',
            name='uq_datastore_org_scope_key'
        ),
        db.Index('ix_datastore_lookup', 'organization_id', 'scope', 'scope_id', 'key'),
        db.Index('ix_datastore_expires', 'expires_at'),
    )

    def to_dict(self):
        return {
            'id': str(self.id),
            'organization_id': str(self.organization_id),
            'scope': self.scope,
            'scope_id': str(self.scope_id) if self.scope_id else None,
            'key': self.key,
            'value': self.value,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
        }

    @classmethod
    def get_value(
        cls,
        organization_id: str,
        key: str,
        scope: str = 'organization',
        scope_id: str = None
    ):
        """
        Obtém valor do datastore.

        Args:
            organization_id: ID da organização
            key: Chave do valor
            scope: Escopo ('organization', 'workflow', 'execution')
            scope_id: ID do workflow ou execution (se aplicável)

        Returns:
            Valor ou None
        """
        query = cls.query.filter_by(
            organization_id=organization_id,
            scope=scope,
            key=key
        )

        if scope_id:
            query = query.filter_by(scope_id=scope_id)
        else:
            query = query.filter(cls.scope_id.is_(None))

        # Verificar expiração
        record = query.first()
        if record:
            if record.expires_at and record.expires_at < datetime.utcnow():
                # Expirado, deletar e retornar None
                db.session.delete(record)
                db.session.commit()
                return None
            return record.value

        return None

    @classmethod
    def set_value(
        cls,
        organization_id: str,
        key: str,
        value,
        scope: str = 'organization',
        scope_id: str = None,
        ttl_seconds: int = None
    ):
        """
        Salva valor no datastore.

        Args:
            organization_id: ID da organização
            key: Chave do valor
            value: Valor a salvar (será serializado como JSON)
            scope: Escopo
            scope_id: ID do workflow ou execution
            ttl_seconds: Tempo de vida em segundos (opcional)
        """
        from datetime import timedelta

        query = cls.query.filter_by(
            organization_id=organization_id,
            scope=scope,
            key=key
        )

        if scope_id:
            query = query.filter_by(scope_id=scope_id)
        else:
            query = query.filter(cls.scope_id.is_(None))

        record = query.first()

        expires_at = None
        if ttl_seconds:
            expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)

        if record:
            record.value = value
            record.updated_at = datetime.utcnow()
            record.expires_at = expires_at
        else:
            record = cls(
                organization_id=organization_id,
                scope=scope,
                scope_id=scope_id,
                key=key,
                value=value,
                expires_at=expires_at
            )
            db.session.add(record)

        db.session.commit()
        return record

    @classmethod
    def delete_value(
        cls,
        organization_id: str,
        key: str,
        scope: str = 'organization',
        scope_id: str = None
    ):
        """Remove valor do datastore"""
        query = cls.query.filter_by(
            organization_id=organization_id,
            scope=scope,
            key=key
        )

        if scope_id:
            query = query.filter_by(scope_id=scope_id)
        else:
            query = query.filter(cls.scope_id.is_(None))

        deleted = query.delete()
        db.session.commit()
        return deleted > 0

    @classmethod
    def cleanup_expired(cls):
        """Remove todos os registros expirados"""
        now = datetime.utcnow()
        deleted = cls.query.filter(
            cls.expires_at.isnot(None),
            cls.expires_at < now
        ).delete()
        db.session.commit()
        return deleted
