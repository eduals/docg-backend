"""
Audit Controller - Endpoint para audit trail.

Feature 6: Auditoria Append-Only
GET /api/v1/executions/{execution_id}/audit
"""
from flask import request, jsonify
from app.controllers.api.v1.executions import bp
from app.models.audit_event import AuditEvent
from app.models.execution import WorkflowExecution


@bp.route('/<execution_id>/audit', methods=['GET'])
def get_audit_trail(execution_id):
    """
    Retorna audit trail de uma execução.

    Query params:
    - cursor: UUID do último evento (para paginação)
    - limit: Máximo de resultados (default 50, max 100)

    Returns:
        {
            'events': [...],
            'next_cursor': 'uuid' ou null
        }
    """
    # Verificar se execução existe
    execution = WorkflowExecution.query.get_or_404(execution_id)

    # Parâmetros de paginação
    cursor = request.args.get('cursor')
    limit = min(int(request.args.get('limit', 50)), 100)

    # Buscar eventos
    events = AuditEvent.get_for_execution(
        target_id=execution_id,
        cursor=cursor,
        limit=limit
    )

    # Determinar próximo cursor
    next_cursor = str(events[-1].id) if events and len(events) == limit else None

    return jsonify({
        'events': [event.to_dict() for event in events],
        'next_cursor': next_cursor
    })
