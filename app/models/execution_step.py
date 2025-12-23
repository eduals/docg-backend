"""
ExecutionStep Model - Rastreia cada step executado em um workflow.

Similar ao ExecutionStep do Automatisch, este model permite:
- Rastreamento completo de cada step executado
- Armazenamento de data_in (parâmetros após computeParameters)
- Armazenamento de data_out (resultado do step)
- Substituição de variáveis entre steps usando {{step.{stepId}.{keyPath}}}
"""
import uuid
from datetime import datetime
from app.database import db
from sqlalchemy.dialects.postgresql import UUID, JSONB


class ExecutionStep(db.Model):
    """
    Representa um step executado dentro de uma WorkflowExecution.

    Cada step guarda:
    - data_in: Parâmetros de entrada após computeParameters (variáveis substituídas)
    - data_out: Dados de saída do step (usados por steps seguintes via {{step.id.field}})
    - status: 'pending', 'running', 'success', 'failure'
    - error_details: Detalhes do erro se status = 'failure'
    """
    __tablename__ = 'execution_steps'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Referência à execução do workflow
    execution_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey('workflow_executions.id', ondelete='CASCADE'),
        nullable=False
    )

    # Referência ao node do workflow
    step_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey('workflow_nodes.id', ondelete='SET NULL'),
        nullable=True
    )

    # Tipo do step (cópia do node_type para facilitar queries)
    step_type = db.Column(db.String(50), nullable=False)

    # Posição no workflow (cópia do position para ordenação)
    position = db.Column(db.Integer, nullable=False)

    # Nome do app que executou (ex: 'hubspot', 'google-docs', 'clicksign')
    app_key = db.Column(db.String(100))

    # Nome da action executada (ex: 'create-contact', 'copy-template')
    action_key = db.Column(db.String(100))

    # === Dados de entrada e saída ===
    # data_in: Parâmetros após substituição de variáveis (computeParameters)
    # Estrutura depende do tipo de step
    data_in = db.Column(JSONB)

    # data_out: Resultado da execução do step
    # Este é o dado que outros steps podem referenciar via {{step.id.field}}
    data_out = db.Column(JSONB)

    # === Status e erro ===
    # Status do step: pending, running, success, failure, skipped
    status = db.Column(db.String(50), default='pending')

    # Detalhes do erro (se status = 'failure')
    error_details = db.Column(db.Text)  # DEPRECATED: usar error_human

    # === Erros separados (F7) ===
    error_human = db.Column(db.Text, nullable=True)  # Mensagem para usuário
    error_tech = db.Column(db.Text, nullable=True)   # Stack trace/detalhes técnicos

    # Código do erro para categorização
    error_code = db.Column(db.String(100))

    # === Timestamps ===
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)

    # Duração em milissegundos (calculado)
    duration_ms = db.Column(db.Integer)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # === Métricas extras (opcional) ===
    # Para steps que fazem chamadas externas
    step_metadata = db.Column(JSONB)
    # Exemplos de metadata:
    # {
    #     "api_calls": 2,
    #     "tokens_used": 150,
    #     "retries": 1,
    #     "external_id": "abc123"
    # }

    # === Relationships ===
    execution = db.relationship(
        'WorkflowExecution',
        backref=db.backref('steps', lazy='dynamic', cascade='all, delete-orphan')
    )

    node = db.relationship('WorkflowNode', foreign_keys=[step_id])

    # === Indexes ===
    __table_args__ = (
        db.Index('idx_execution_step_execution', 'execution_id'),
        db.Index('idx_execution_step_position', 'execution_id', 'position'),
        db.Index('idx_execution_step_status', 'execution_id', 'status'),
        db.Index('idx_execution_step_step_id', 'step_id'),
    )

    def to_dict(self, include_data=True):
        """Converte para dicionário"""
        result = {
            'id': str(self.id),
            'execution_id': str(self.execution_id),
            'step_id': str(self.step_id) if self.step_id else None,
            'step_type': self.step_type,
            'position': self.position,
            'app_key': self.app_key,
            'action_key': self.action_key,
            'status': self.status,
            'error_details': self.error_details,  # DEPRECATED
            'error_human': self.error_human,      # F7
            'error_tech': self.error_tech,        # F7
            'error_code': self.error_code,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'duration_ms': self.duration_ms,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

        if include_data:
            result['data_in'] = self.data_in
            result['data_out'] = self.data_out
            result['step_metadata'] = self.step_metadata

        return result

    def start(self):
        """Marca o step como iniciado"""
        self.status = 'running'
        self.started_at = datetime.utcnow()

    def complete(self, data_out: dict = None, step_metadata: dict = None):
        """Marca o step como concluído com sucesso"""
        self.status = 'success'
        self.completed_at = datetime.utcnow()
        if data_out is not None:
            self.data_out = data_out
        if step_metadata is not None:
            self.step_metadata = step_metadata
        self._calculate_duration()

    def fail(self, error_details: str, error_code: str = None, error_human: str = None, error_tech: str = None):
        """
        Marca o step como falho.

        Args:
            error_details: Mensagem de erro (DEPRECATED, usar error_human/error_tech)
            error_code: Código do erro
            error_human: Mensagem para usuário
            error_tech: Detalhes técnicos/stack trace
        """
        self.status = 'failure'
        self.completed_at = datetime.utcnow()

        # Backward compatibility
        self.error_details = error_details

        # Novos campos (F7)
        self.error_human = error_human or error_details
        self.error_tech = error_tech

        self.error_code = error_code
        self._calculate_duration()

    def skip(self, reason: str = None):
        """Marca o step como pulado (ex: condição não atendida)"""
        self.status = 'skipped'
        self.completed_at = datetime.utcnow()
        if reason:
            self.error_details = reason
        self._calculate_duration()

    def _calculate_duration(self):
        """Calcula duração em milissegundos"""
        if self.started_at and self.completed_at:
            delta = self.completed_at - self.started_at
            self.duration_ms = int(delta.total_seconds() * 1000)

    def get_output_value(self, key_path: str):
        """
        Obtém um valor do data_out usando um key path.

        Exemplo: get_output_value('contact.id') retorna data_out['contact']['id']

        Args:
            key_path: Caminho separado por pontos (ex: 'contact.id', 'document.url')

        Returns:
            O valor encontrado ou None se não existir
        """
        if not self.data_out:
            return None

        keys = key_path.split('.')
        value = self.data_out

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            elif isinstance(value, list):
                try:
                    index = int(key)
                    value = value[index]
                except (ValueError, IndexError):
                    return None
            else:
                return None

        return value

    @classmethod
    def create_for_node(cls, execution_id, node, data_in: dict = None):
        """
        Factory method para criar ExecutionStep a partir de um WorkflowNode.

        Args:
            execution_id: UUID da WorkflowExecution
            node: WorkflowNode sendo executado
            data_in: Parâmetros de entrada após computeParameters

        Returns:
            Nova instância de ExecutionStep
        """
        return cls(
            execution_id=execution_id,
            step_id=node.id,
            step_type=node.node_type,
            position=node.position,
            data_in=data_in,
            status='pending'
        )

    @classmethod
    def get_by_execution(cls, execution_id, status: str = None):
        """
        Obtém todos os steps de uma execução, ordenados por posição.

        Args:
            execution_id: UUID da execução
            status: Filtrar por status (opcional)

        Returns:
            Lista de ExecutionSteps ordenados por position
        """
        query = cls.query.filter_by(execution_id=execution_id)

        if status:
            query = query.filter_by(status=status)

        return query.order_by(cls.position).all()

    @classmethod
    def get_previous_steps(cls, execution_id, position: int):
        """
        Obtém todos os steps anteriores a uma posição (para computeParameters).

        Args:
            execution_id: UUID da execução
            position: Posição atual

        Returns:
            Lista de ExecutionSteps com position < position atual
        """
        return cls.query.filter(
            cls.execution_id == execution_id,
            cls.position < position,
            cls.status == 'success'
        ).order_by(cls.position).all()
