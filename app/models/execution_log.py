"""
ExecutionLog Model - Logs estruturados de execução.

Feature 5: Logs Estruturados
- Separação de mensagens humanas vs técnicas
- Logs consultáveis por execution, step, level, domain
- Correlation ID para rastreamento
"""
import uuid
from datetime import datetime
from app.database import db
from sqlalchemy.dialects.postgresql import UUID


class ExecutionLog(db.Model):
    """
    Logs estruturados de execução de workflows.

    Cada log registra um evento durante a execução, com:
    - Mensagem humana (para UI) e detalhes técnicos (para debug)
    - Level (ok, warn, error)
    - Domain (preflight, step, delivery, signature)
    - Correlation ID para rastrear toda a execução
    """
    __tablename__ = 'execution_logs'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Referências
    execution_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey('workflow_executions.id', ondelete='CASCADE'),
        nullable=False
    )
    step_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey('execution_steps.id', ondelete='SET NULL'),
        nullable=True
    )

    # Timestamp
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Nível do log
    level = db.Column(db.String(10), nullable=False, index=True)  # ok, warn, error

    # Domínio/categoria
    domain = db.Column(db.String(50), nullable=False, index=True)  # preflight, step, delivery, signature

    # Mensagens
    message_human = db.Column(db.Text, nullable=False)  # "Documento gerado com sucesso"
    details_tech = db.Column(db.Text, nullable=True)    # Stack trace, response body, debug info

    # Correlation ID (para rastrear toda a cadeia)
    correlation_id = db.Column(UUID(as_uuid=True), nullable=False, index=True)

    # Relacionamentos
    execution = db.relationship(
        'WorkflowExecution',
        backref=db.backref('logs', lazy='dynamic', cascade='all, delete-orphan')
    )
    step = db.relationship('ExecutionStep', foreign_keys=[step_id])

    # Índices compostos
    __table_args__ = (
        db.Index('idx_execution_logs_execution_id', 'execution_id'),
        db.Index('idx_execution_logs_level', 'level'),
        db.Index('idx_execution_logs_domain', 'domain'),
        db.Index('idx_execution_logs_correlation_id', 'correlation_id'),
        db.Index('idx_execution_logs_timestamp', 'timestamp'),
        db.Index('idx_execution_logs_exec_level', 'execution_id', 'level'),
        db.Index('idx_execution_logs_exec_domain', 'execution_id', 'domain'),
    )

    def to_dict(self):
        """Converte para dicionário"""
        return {
            'id': str(self.id),
            'execution_id': str(self.execution_id),
            'step_id': str(self.step_id) if self.step_id else None,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'level': self.level,
            'domain': self.domain,
            'message_human': self.message_human,
            'details_tech': self.details_tech,
            'correlation_id': str(self.correlation_id)
        }

    @classmethod
    def create(
        cls,
        execution_id: str,
        correlation_id: str,
        level: str,
        domain: str,
        message_human: str,
        details_tech: str = None,
        step_id: str = None
    ):
        """
        Factory method para criar log.

        Args:
            execution_id: UUID da execução
            correlation_id: UUID de correlação
            level: 'ok', 'warn', ou 'error'
            domain: 'preflight', 'step', 'delivery', 'signature', etc
            message_human: Mensagem para o usuário
            details_tech: Detalhes técnicos (opcional)
            step_id: UUID do step (opcional)

        Returns:
            Nova instância de ExecutionLog
        """
        return cls(
            execution_id=execution_id,
            correlation_id=correlation_id,
            level=level,
            domain=domain,
            message_human=message_human,
            details_tech=details_tech,
            step_id=step_id
        )

    @classmethod
    def get_for_execution(
        cls,
        execution_id: str,
        level: str = None,
        domain: str = None,
        cursor: str = None,
        limit: int = 50
    ):
        """
        Busca logs de uma execução com filtros.

        Args:
            execution_id: UUID da execução
            level: Filtrar por nível (opcional)
            domain: Filtrar por domínio (opcional)
            cursor: UUID do último log (para paginação)
            limit: Máximo de resultados (default 50, max 100)

        Returns:
            Lista de ExecutionLog ordenados por timestamp
        """
        query = cls.query.filter_by(execution_id=execution_id)

        if level:
            query = query.filter_by(level=level)

        if domain:
            query = query.filter_by(domain=domain)

        if cursor:
            # Paginação por cursor (UUID)
            cursor_log = cls.query.get(cursor)
            if cursor_log:
                query = query.filter(cls.timestamp > cursor_log.timestamp)

        limit = min(limit, 100)  # Max 100 por request

        return query.order_by(cls.timestamp).limit(limit).all()
