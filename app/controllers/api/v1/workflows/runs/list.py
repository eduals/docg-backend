"""
List Workflow Runs Controller.
"""

from flask import request, jsonify, g
from app.models import Workflow, WorkflowExecution, WorkflowNode


def list_workflow_runs(workflow_id: str):
    """
    Lista execuções (runs) de um workflow.

    Query params:
    - limit: Número máximo de execuções (default: 50, max: 100)
    - status: Filtrar por status (running, completed, failed)
    - offset: Paginação (default: 0)
    """
    workflow = Workflow.query.filter_by(
        id=workflow_id,
        organization_id=g.organization_id
    ).first_or_404()

    # Parâmetros de paginação
    limit = min(int(request.args.get('limit', 50)), 100)
    offset = int(request.args.get('offset', 0))
    status_filter = request.args.get('status')

    # Buscar execuções
    query = WorkflowExecution.query.filter_by(workflow_id=workflow.id)

    if status_filter:
        status_mapping = {
            'running': 'running',
            'success': 'completed',
            'error': 'failed',
            'pending': 'running'
        }
        backend_status = status_mapping.get(status_filter.lower())
        if backend_status:
            query = query.filter_by(status=backend_status)

    total_count = query.count()
    executions = query.order_by(WorkflowExecution.started_at.desc()).offset(offset).limit(limit).all()

    # Buscar nodes do workflow para calcular steps
    nodes = WorkflowNode.query.filter_by(
        workflow_id=workflow.id
    ).order_by(WorkflowNode.position).all()
    total_steps = len([n for n in nodes if not n.is_trigger()])

    # Converter para formato esperado
    runs = []
    for execution in executions:
        status_mapping = {
            'completed': 'success',
            'failed': 'error',
            'running': 'running'
        }
        interface_status = status_mapping.get(execution.status, 'pending')

        steps_completed = _calculate_steps_completed(execution, nodes, total_steps)
        trigger_source = execution.trigger_type or 'manual'

        run_dict = {
            'id': str(execution.id),
            'status': interface_status,
            'started_at': execution.started_at.isoformat() if execution.started_at else None,
            'completed_at': execution.completed_at.isoformat() if execution.completed_at else None,
            'duration_ms': execution.execution_time_ms,
            'trigger_source': trigger_source,
            'trigger_data': execution.trigger_data,
            'error_message': execution.error_message,
            'steps_completed': steps_completed,
            'steps_total': total_steps if total_steps > 0 else None
        }

        runs.append(run_dict)

    return jsonify({
        'runs': runs,
        'pagination': {
            'total': total_count,
            'limit': limit,
            'offset': offset,
            'has_more': (offset + limit) < total_count
        }
    })


def _calculate_steps_completed(execution, nodes, total_steps):
    """Calcula quantos steps foram completados"""
    if execution.status == 'completed':
        return total_steps
    elif execution.status == 'failed':
        if execution.execution_logs:
            completed_nodes = [log for log in execution.execution_logs
                             if log.get('status') in ['success', 'failed']]
            return len(completed_nodes)
        return 0
    elif execution.status == 'running':
        if execution.current_node_id:
            current_node = next((n for n in nodes if str(n.id) == str(execution.current_node_id)), None)
            if current_node:
                return len([n for n in nodes
                           if n.position < current_node.position and not n.is_trigger()])
        elif execution.execution_logs:
            completed_nodes = [log for log in execution.execution_logs
                             if log.get('status') in ['success', 'failed']]
            return len(completed_nodes)
    return None
