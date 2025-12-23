"""
SSE Publisher - Publica eventos no Redis para SSE
"""
import os
import json
import redis
from datetime import datetime
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class SSEPublisher:
    """
    Singleton para publicar eventos SSE via Redis Pub/Sub.
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
            logger.info("SSE Publisher conectado ao Redis")
        except redis.ConnectionError as e:
            logger.warning(f"Redis nao disponivel para SSE: {e}")
            self._redis = None

    def _get_channel(self, execution_id: str) -> str:
        return f"execution:{execution_id}"

    def publish(self, execution_id: str, event_type: str, data: Dict[str, Any]) -> bool:
        """
        Publica evento no Redis.

        Args:
            execution_id: ID da execucao
            event_type: Tipo do evento (step:started, step:completed, etc)
            data: Dados do evento

        Returns:
            True se publicou com sucesso
        """
        if not self._redis:
            return False

        try:
            channel = self._get_channel(execution_id)
            message = json.dumps({
                "type": event_type,
                "data": data,
                "timestamp": datetime.utcnow().isoformat()
            })
            self._redis.publish(channel, message)
            logger.debug(f"SSE evento {event_type} publicado para {channel}")
            return True
        except Exception as e:
            logger.error(f"Erro ao publicar evento SSE: {e}")
            return False

    def step_started(self, execution_id: str, node_id: str, node_type: str, position: int):
        """Emite evento de step iniciado."""
        self.publish(execution_id, "step:started", {
            "node_id": node_id,
            "node_type": node_type,
            "position": position,
            "started_at": datetime.utcnow().isoformat()
        })

    def step_completed(self, execution_id: str, node_id: str, node_type: str,
                       position: int, started_at: str, output: dict = None):
        """Emite evento de step completado."""
        completed_at = datetime.utcnow()
        try:
            started = datetime.fromisoformat(started_at) if isinstance(started_at, str) else started_at
            duration_ms = int((completed_at - started).total_seconds() * 1000)
        except:
            duration_ms = 0

        self.publish(execution_id, "step:completed", {
            "node_id": node_id,
            "node_type": node_type,
            "position": position,
            "started_at": started_at,
            "completed_at": completed_at.isoformat(),
            "duration_ms": duration_ms,
            "output": output
        })

    def step_failed(self, execution_id: str, node_id: str, node_type: str,
                    position: int, started_at: str, error: str):
        """Emite evento de step falho."""
        self.publish(execution_id, "step:failed", {
            "node_id": node_id,
            "node_type": node_type,
            "position": position,
            "started_at": started_at,
            "completed_at": datetime.utcnow().isoformat(),
            "error": error
        })

    def execution_completed(self, execution_id: str, execution_time_ms: int,
                            generated_document_id: str = None):
        """Emite evento de workflow completado."""
        self.publish(execution_id, "execution:completed", {
            "execution_id": execution_id,
            "status": "completed",
            "completed_at": datetime.utcnow().isoformat(),
            "execution_time_ms": execution_time_ms,
            "generated_document_id": generated_document_id
        })

    def execution_failed(self, execution_id: str, error_message: str):
        """Emite evento de workflow falho."""
        self.publish(execution_id, "execution:failed", {
            "execution_id": execution_id,
            "status": "failed",
            "error_message": error_message,
            "completed_at": datetime.utcnow().isoformat()
        })

    def execution_paused(self, execution_id: str, reason: str, waiting_for: dict = None):
        """Emite evento de workflow pausado."""
        self.publish(execution_id, "execution:paused", {
            "execution_id": execution_id,
            "reason": reason,
            "waiting_for": waiting_for or {}
        })


def get_sse_publisher() -> SSEPublisher:
    """Helper para obter instancia do publisher."""
    return SSEPublisher.get_instance()
