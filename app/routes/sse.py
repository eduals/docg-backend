"""
SSE Routes - Server-Sent Events com Redis Streams e replay.

Features 3 & 4:
- F3: Schema v1 padronizado
- F4: Replay de eventos via Last-Event-ID
"""
import os
import json
import redis
from flask import Blueprint, Response, g, request
from app.utils.auth import require_auth, require_org
from app.models import WorkflowExecution, Workflow
import logging

logger = logging.getLogger(__name__)

sse_bp = Blueprint('sse', __name__, url_prefix='/api/v1/sse')


def event_stream(execution_id: str, last_event_id: str = None):
    """
    Generator que consome Redis Stream e envia eventos SSE.

    Features:
    - Replay de eventos perdidos via Last-Event-ID
    - Schema v1 padronizado
    - Persistência de eventos (últimos 1000)

    Args:
        execution_id: UUID da execução
        last_event_id: ID do último evento recebido (para replay)

    Yields:
        Eventos SSE formatados
    """
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

    try:
        r = redis.Redis.from_url(redis_url, decode_responses=True)
        stream_key = f"docg:exec:{execution_id}"

        logger.info(f"SSE: Cliente conectado ao stream {stream_key}")

        # Evento inicial de conexão
        yield f"event: connected\ndata: {json.dumps({'execution_id': execution_id})}\n\n"

        # === Replay de eventos perdidos ===
        # Se Last-Event-ID fornecido, enviar eventos desde esse ID
        if last_event_id and last_event_id != '0':
            logger.info(f"SSE: Replay desde {last_event_id}")

            # XREAD com last_event_id como cursor
            missed_events = r.xread({stream_key: last_event_id}, count=100)

            for stream, events in missed_events:
                for event_id, event_data in events:
                    event_json = json.loads(event_data['event'])
                    event_type = event_json.get('event_type', 'update')

                    yield f"id: {event_id}\n"
                    yield f"event: {event_type}\n"
                    yield f"data: {json.dumps(event_json)}\n\n"

        # === Streaming de novos eventos ===
        # Cursor inicial: último evento replay ou '0' para começar do início
        cursor = last_event_id if last_event_id else '0'

        while True:
            # XREAD com bloqueio de 5 segundos
            # count=10 para enviar eventos em batches
            events = r.xread({stream_key: cursor}, block=5000, count=10)

            if not events:
                # Timeout: enviar heartbeat
                yield f"event: heartbeat\ndata: {json.dumps({'timestamp': 'now'})}\n\n"
                continue

            for stream, event_list in events:
                for event_id, event_data in event_list:
                    event_json = json.loads(event_data['event'])
                    event_type = event_json.get('event_type', 'update')

                    # Enviar evento com ID para replay
                    yield f"id: {event_id}\n"
                    yield f"event: {event_type}\n"
                    yield f"data: {json.dumps(event_json)}\n\n"

                    # Atualizar cursor
                    cursor = event_id

                    # Se execução finalizou, fechar stream
                    if event_type in ['execution.completed', 'execution.failed', 'execution.canceled']:
                        logger.info(f"SSE: Execução {execution_id} finalizada, fechando stream")
                        return

    except redis.ConnectionError as e:
        logger.error(f"SSE: Erro de conexão Redis: {e}")
        yield f"event: error\ndata: {json.dumps({'error': 'Redis connection error'})}\n\n"
    except GeneratorExit:
        logger.info(f"SSE: Cliente desconectou de {execution_id}")
    except Exception as e:
        logger.error(f"SSE: Erro inesperado: {e}")
        yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"


@sse_bp.route('/executions/<execution_id>/stream', methods=['GET'])
@require_auth
@require_org
def stream_execution(execution_id):
    """
    SSE endpoint para acompanhar execução de workflow em tempo real.

    Features:
    - Replay automático de eventos perdidos via Last-Event-ID
    - Schema v1 padronizado
    - Heartbeat para manter conexão alive

    GET /api/v1/sse/executions/<execution_id>/stream

    Headers:
        Authorization: Bearer <token>
        X-Organization-ID: <org_id>
        Last-Event-ID: <event_id>  # Opcional, para replay

    Response: text/event-stream

    Eventos (Schema v1):
        - execution.created
        - execution.status_changed
        - execution.progress
        - preflight.completed
        - step.started
        - step.completed
        - step.failed
        - execution.completed
        - execution.failed
        - execution.canceled
        - signature.requested
        - signature.completed

    Exemplo de evento:
        id: 1234567890-0
        event: step.completed
        data: {
            "schema_version": 1,
            "event_id": "uuid",
            "event_type": "step.completed",
            "timestamp": "2025-12-23T10:30:00.000Z",
            "execution_id": "uuid",
            "workflow_id": "uuid",
            "organization_id": "uuid",
            "status": "running",
            "progress": 45,
            "current_step": {...},
            "data": {...}
        }
    """
    # Validar que execução existe e pertence à organização
    execution = WorkflowExecution.query.get(execution_id)
    if not execution:
        return {"error": "Execução não encontrada"}, 404

    workflow = Workflow.query.get(execution.workflow_id)
    if not workflow or str(workflow.organization_id) != str(g.organization_id):
        return {"error": "Execução não pertence a esta organização"}, 403

    # Obter Last-Event-ID do header (se fornecido)
    last_event_id = request.headers.get('Last-Event-ID')

    return Response(
        event_stream(execution_id, last_event_id),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
            'Access-Control-Allow-Origin': '*'
        }
    )


@sse_bp.route('/health', methods=['GET'])
def sse_health():
    """Health check para SSE service"""
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    try:
        r = redis.Redis.from_url(redis_url)
        r.ping()
        return {"status": "healthy", "redis": "connected", "mode": "streams"}
    except redis.ConnectionError:
        return {"status": "unhealthy", "redis": "disconnected"}, 503
