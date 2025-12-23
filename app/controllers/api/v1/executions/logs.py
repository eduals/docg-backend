"""
Logs Controller - Endpoint para consultar logs de execução.

Feature 5: Logs Estruturados
GET /api/v1/executions/{execution_id}/logs
"""
from flask import request, jsonify
from app.controllers.api.v1.executions import bp
from app.models.execution_log import ExecutionLog
from app.models.execution import WorkflowExecution


@bp.route('/<execution_id>/logs', methods=['GET'])
def get_logs(execution_id):
    """
    Retorna logs estruturados de uma execução.

    Query params:
    - level: Filtrar por nível (ok, warn, error)
    - domain: Filtrar por domínio (preflight, step, delivery, signature)
    - cursor: UUID do último log (para paginação)
    - limit: Máximo de resultados (default 50, max 100)

    Returns:
        {
            'logs': [...],
            'next_cursor': 'uuid' ou null
        }
    """
    # Verificar se execução existe
    execution = WorkflowExecution.query.get_or_404(execution_id)

    # Parâmetros de filtro
    level = request.args.get('level')
    domain = request.args.get('domain')
    cursor = request.args.get('cursor')
    limit = min(int(request.args.get('limit', 50)), 100)

    # Buscar logs
    logs = ExecutionLog.get_for_execution(
        execution_id=execution_id,
        level=level,
        domain=domain,
        cursor=cursor,
        limit=limit
    )

    # Determinar próximo cursor
    next_cursor = str(logs[-1].id) if logs and len(logs) == limit else None

    return jsonify({
        'logs': [log.to_dict() for log in logs],
        'next_cursor': next_cursor
    })
