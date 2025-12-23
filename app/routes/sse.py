"""
SSE Routes - Server-Sent Events para real-time updates
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


def event_stream(execution_id: str):
    """
    Generator que faz subscribe no Redis e envia eventos SSE.
    """
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

    try:
        r = redis.Redis.from_url(redis_url, decode_responses=True)
        pubsub = r.pubsub()
        channel = f"execution:{execution_id}"
        pubsub.subscribe(channel)

        logger.info(f"SSE: Cliente conectado ao channel {channel}")

        # Evento inicial de conexao
        yield f"event: connected\ndata: {json.dumps({'execution_id': execution_id})}\n\n"

        # Buscar estado atual e enviar logs existentes como catch-up
        from flask import current_app
        with current_app.app_context():
            execution = WorkflowExecution.query.get(execution_id)
            if execution and execution.execution_logs:
                for log in execution.execution_logs:
                    status = log.get('status', 'unknown')
                    if status == 'success':
                        event_type = 'step:completed'
                    elif status == 'error':
                        event_type = 'step:failed'
                    else:
                        event_type = f'step:{status}'
                    yield f"event: {event_type}\ndata: {json.dumps(log)}\n\n"

        # Loop de eventos
        for message in pubsub.listen():
            if message['type'] == 'message':
                data = json.loads(message['data'])
                event_type = data.get('type', 'update')
                yield f"event: {event_type}\ndata: {json.dumps(data)}\n\n"

                # Se execucao finalizou, fechar stream
                if event_type in ['execution:completed', 'execution:failed']:
                    logger.info(f"SSE: Execucao {execution_id} finalizada, fechando stream")
                    break

    except redis.ConnectionError as e:
        logger.error(f"SSE: Erro de conexao Redis: {e}")
        yield f"event: error\ndata: {json.dumps({'error': 'Redis connection error'})}\n\n"
    except GeneratorExit:
        logger.info(f"SSE: Cliente desconectou")
    finally:
        try:
            pubsub.unsubscribe()
            pubsub.close()
        except:
            pass


@sse_bp.route('/executions/<execution_id>/stream', methods=['GET'])
@require_auth
@require_org
def stream_execution(execution_id):
    """
    SSE endpoint para acompanhar execucao de workflow em tempo real.

    GET /api/v1/sse/executions/<execution_id>/stream

    Headers:
        Authorization: Bearer <token>
        X-Organization-ID: <org_id>

    Ou via query params (para EventSource que nao suporta headers):
        ?Authorization=Bearer <token>&organization_id=<org_id>

    Response: text/event-stream

    Events:
        - connected: Conexao estabelecida
        - step:started: Step iniciou
        - step:completed: Step completou
        - step:failed: Step falhou
        - execution:completed: Workflow finalizou
        - execution:failed: Workflow falhou
        - execution:paused: Workflow pausado
    """
    # Validar que execucao existe e pertence a organizacao
    execution = WorkflowExecution.query.get(execution_id)
    if not execution:
        return {"error": "Execucao nao encontrada"}, 404

    workflow = Workflow.query.get(execution.workflow_id)
    if not workflow or str(workflow.organization_id) != str(g.organization_id):
        return {"error": "Execucao nao pertence a esta organizacao"}, 403

    return Response(
        event_stream(execution_id),
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
        return {"status": "healthy", "redis": "connected"}
    except redis.ConnectionError:
        return {"status": "unhealthy", "redis": "disconnected"}, 503
