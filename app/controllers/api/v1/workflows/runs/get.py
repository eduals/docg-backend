"""
Get Workflow Run Controller.
"""

from flask import request, jsonify, g
from app.models import Workflow, WorkflowExecution, WorkflowNode


def get_workflow_run(workflow_id: str, run_id: str):
    """
    Retorna detalhes de uma execução específica.

    Query params:
    - include_logs: Incluir execution_logs na resposta (default: false)
    """
    workflow = Workflow.query.filter_by(
        id=workflow_id,
        organization_id=g.organization_id
    ).first_or_404()

    execution = WorkflowExecution.query.filter_by(
        id=run_id,
        workflow_id=workflow.id
    ).first_or_404()

    # Buscar nodes do workflow
    nodes = WorkflowNode.query.filter_by(
        workflow_id=workflow.id
    ).order_by(WorkflowNode.position).all()
    total_steps = len([n for n in nodes if not n.is_trigger()])

    # Mapear status
    status_mapping = {
        'completed': 'success',
        'failed': 'error',
        'running': 'running'
    }
    interface_status = status_mapping.get(execution.status, 'pending')

    steps_completed = _calculate_steps_completed(execution, nodes, total_steps)

    # Buscar informações do node atual
    current_node_info = None
    if execution.current_node_id:
        current_node = WorkflowNode.query.get(execution.current_node_id)
        if current_node:
            current_node_info = {
                'id': str(current_node.id),
                'node_type': current_node.node_type,
                'position': current_node.position,
                'name': current_node.config.get('name') if current_node.config else None
            }

    include_logs = request.args.get('include_logs', 'false').lower() == 'true'
    trigger_source = execution.trigger_type or 'manual'

    run_dict = {
        'id': str(execution.id),
        'workflow_id': str(execution.workflow_id),
        'status': interface_status,
        'started_at': execution.started_at.isoformat() if execution.started_at else None,
        'completed_at': execution.completed_at.isoformat() if execution.completed_at else None,
        'duration_ms': execution.execution_time_ms,
        'trigger_source': trigger_source,
        'trigger_data': execution.trigger_data,
        'error_message': execution.error_message,
        'steps_completed': steps_completed,
        'steps_total': total_steps if total_steps > 0 else None,
        'generated_document_id': str(execution.generated_document_id) if execution.generated_document_id else None,
        'ai_metrics': execution.ai_metrics,
        'current_node_id': str(execution.current_node_id) if execution.current_node_id else None,
        'current_node': current_node_info,
        'temporal_workflow_id': execution.temporal_workflow_id,
        'temporal_run_id': execution.temporal_run_id
    }

    if include_logs:
        run_dict['execution_logs'] = execution.execution_logs or []

    return jsonify(run_dict)


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
