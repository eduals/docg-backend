"""
SSE Publisher - Publica eventos no Redis Streams com schema versionado.

Features 3 & 4:
- F3: SSE Schema v1 (padronizado, versionado)
- F4: Redis Streams (replay, persistência)
"""
import os
import json
import uuid
import redis
from datetime import datetime
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

# Configurações
REDIS_STREAM_MAXLEN = int(os.getenv('REDIS_STREAM_MAXLEN', 1000))
REDIS_STREAM_TTL = int(os.getenv('REDIS_STREAM_TTL', 86400))  # 24h


class SSEPublisher:
    """
    Publisher para eventos SSE via Redis Streams.

    Features:
    - Schema v1 padronizado
    - Replay de eventos (Last-Event-ID)
    - Persistência com maxlen e TTL
    """
    _instance: Optional['SSEPublisher'] = None
    _redis: Optional[redis.Redis] = None

    @classmethod
    def get_instance(cls) -> 'SSEPublisher':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        try:
            self._redis = redis.Redis.from_url(redis_url, decode_responses=True)
            self._redis.ping()
            logger.info("SSE Publisher conectado ao Redis (Streams)")
        except redis.ConnectionError as e:
            logger.warning(f"Redis não disponível para SSE: {e}")
            self._redis = None

    def _get_stream_key(self, execution_id: str) -> str:
        """Retorna chave do Redis Stream"""
        return f"docg:exec:{execution_id}"

    def publish_v1(
        self,
        execution_id: str,
        event_type: str,
        status: str,
        progress: int,
        current_step: Optional[Dict] = None,
        data: Optional[Dict] = None,
        workflow_id: str = None,
        organization_id: str = None
    ) -> bool:
        """
        Publica evento com Schema v1.

        Schema v1:
        {
            "schema_version": 1,
            "event_id": "uuid",
            "event_type": "step.completed",
            "timestamp": "ISO",
            "execution_id": "uuid",
            "workflow_id": "uuid",
            "organization_id": "uuid",
            "status": "running",
            "progress": 45,
            "current_step": {...},
            "data": {...}
        }

        Args:
            execution_id: UUID da execução
            event_type: Tipo do evento (ex: 'step.completed', 'execution.status_changed')
            status: Status atual da execução
            progress: Progresso (0-100)
            current_step: Step atual (index, label, node_id, node_type)
            data: Dados específicos do evento
            workflow_id: UUID do workflow
            organization_id: UUID da organização

        Returns:
            True se publicou com sucesso
        """
        if not self._redis:
            return False

        try:
            event = {
                "schema_version": 1,
                "event_id": str(uuid.uuid4()),
                "event_type": event_type,
                "timestamp": datetime.utcnow().isoformat(),
                # Contexto
                "execution_id": execution_id,
                "workflow_id": workflow_id,
                "organization_id": organization_id,
                # Estado atual
                "status": status,
                "progress": progress,
                "current_step": current_step,
                # Dados do evento
                "data": data or {}
            }

            stream_key = self._get_stream_key(execution_id)

            # XADD com maxlen para limitar tamanho
            event_id = self._redis.xadd(
                name=stream_key,
                fields={"event": json.dumps(event)},
                maxlen=REDIS_STREAM_MAXLEN,
                approximate=True  # ~1000 para performance
            )

            # Definir TTL no stream (expira após 24h)
            self._redis.expire(stream_key, REDIS_STREAM_TTL)

            logger.debug(f"SSE evento {event_type} publicado: {event_id}")
            return True

        except Exception as e:
            logger.error(f"Erro ao publicar evento SSE: {e}")
            return False

    # === Helper methods com schema v1 ===

    def execution_created(self, execution_id: str, workflow_id: str, organization_id: str, trigger_type: str, trigger_data: dict):
        """Emite evento de execução criada"""
        self.publish_v1(
            execution_id=execution_id,
            event_type="execution.created",
            status="queued",
            progress=0,
            current_step=None,
            data={
                "trigger_type": trigger_type,
                "trigger_data": trigger_data
            },
            workflow_id=workflow_id,
            organization_id=organization_id
        )

    def execution_status_changed(self, execution_id: str, workflow_id: str, organization_id: str,
                                   from_status: str, to_status: str, reason: str = None, progress: int = 0):
        """Emite evento de mudança de status"""
        self.publish_v1(
            execution_id=execution_id,
            event_type="execution.status_changed",
            status=to_status,
            progress=progress,
            current_step=None,
            data={
                "from": from_status,
                "to": to_status,
                "reason": reason
            },
            workflow_id=workflow_id,
            organization_id=organization_id
        )

    def execution_progress(self, execution_id: str, workflow_id: str, organization_id: str,
                            progress: int, current_step: dict, status: str = "running"):
        """Emite evento de progresso atualizado"""
        self.publish_v1(
            execution_id=execution_id,
            event_type="execution.progress",
            status=status,
            progress=progress,
            current_step=current_step,
            data={"progress": progress},
            workflow_id=workflow_id,
            organization_id=organization_id
        )

    def preflight_completed(self, execution_id: str, workflow_id: str, organization_id: str,
                             blocking_count: int, warning_count: int, groups: dict, status: str = "needs_review"):
        """Emite evento de preflight concluído"""
        self.publish_v1(
            execution_id=execution_id,
            event_type="preflight.completed",
            status=status,
            progress=0,
            current_step=None,
            data={
                "blocking_count": blocking_count,
                "warning_count": warning_count,
                "groups": groups
            },
            workflow_id=workflow_id,
            organization_id=organization_id
        )

    def step_started(self, execution_id: str, workflow_id: str, organization_id: str,
                      node_id: str, node_type: str, position: int, label: str, progress: int):
        """Emite evento de step iniciado"""
        self.publish_v1(
            execution_id=execution_id,
            event_type="step.started",
            status="running",
            progress=progress,
            current_step={
                "index": position,
                "label": label,
                "node_id": node_id,
                "node_type": node_type
            },
            data={
                "node_id": node_id,
                "node_type": node_type,
                "position": position
            },
            workflow_id=workflow_id,
            organization_id=organization_id
        )

    def step_completed(self, execution_id: str, workflow_id: str, organization_id: str,
                        node_id: str, node_type: str, duration_ms: int, output_preview: dict, progress: int):
        """Emite evento de step completado"""
        self.publish_v1(
            execution_id=execution_id,
            event_type="step.completed",
            status="running",
            progress=progress,
            current_step=None,
            data={
                "node_id": node_id,
                "node_type": node_type,
                "duration_ms": duration_ms,
                "output_preview": output_preview
            },
            workflow_id=workflow_id,
            organization_id=organization_id
        )

    def step_failed(self, execution_id: str, workflow_id: str, organization_id: str,
                     node_id: str, error_human: str, error_tech: str, progress: int):
        """Emite evento de step falho"""
        self.publish_v1(
            execution_id=execution_id,
            event_type="step.failed",
            status="running",
            progress=progress,
            current_step=None,
            data={
                "node_id": node_id,
                "error_human": error_human,
                "error_tech": error_tech
            },
            workflow_id=workflow_id,
            organization_id=organization_id
        )

    def execution_completed(self, execution_id: str, workflow_id: str, organization_id: str):
        """Emite evento de execução completada"""
        self.publish_v1(
            execution_id=execution_id,
            event_type="execution.completed",
            status="completed",
            progress=100,
            current_step=None,
            data={},
            workflow_id=workflow_id,
            organization_id=organization_id
        )

    def execution_failed(self, execution_id: str, workflow_id: str, organization_id: str,
                          error_human: str, error_tech: str):
        """Emite evento de execução falha"""
        self.publish_v1(
            execution_id=execution_id,
            event_type="execution.failed",
            status="failed",
            progress=0,
            current_step=None,
            data={
                "error_human": error_human,
                "error_tech": error_tech
            },
            workflow_id=workflow_id,
            organization_id=organization_id
        )

    def execution_canceled(self, execution_id: str, workflow_id: str, organization_id: str,
                            canceled_by: str, reason: str):
        """Emite evento de execução cancelada"""
        self.publish_v1(
            execution_id=execution_id,
            event_type="execution.canceled",
            status="canceled",
            progress=0,
            current_step=None,
            data={
                "canceled_by": canceled_by,
                "reason": reason
            },
            workflow_id=workflow_id,
            organization_id=organization_id
        )

    def signature_requested(self, execution_id: str, workflow_id: str, organization_id: str,
                             envelope_id: str, signers: list, progress: int):
        """Emite evento de assinatura solicitada"""
        self.publish_v1(
            execution_id=execution_id,
            event_type="signature.requested",
            status="signing",
            progress=progress,
            current_step=None,
            data={
                "envelope_id": envelope_id,
                "signers": signers
            },
            workflow_id=workflow_id,
            organization_id=organization_id
        )

    def signature_completed(self, execution_id: str, workflow_id: str, organization_id: str,
                             envelope_id: str, signed_at: str):
        """Emite evento de assinatura concluída"""
        self.publish_v1(
            execution_id=execution_id,
            event_type="signature.completed",
            status="signed",
            progress=100,
            current_step=None,
            data={
                "envelope_id": envelope_id,
                "signed_at": signed_at
            },
            workflow_id=workflow_id,
            organization_id=organization_id
        )


def get_sse_publisher() -> SSEPublisher:
    """Helper para obter instância do publisher."""
    return SSEPublisher.get_instance()
