"""
Control Controller - Endpoints para controle de execução.

Feature 10: Pause/Resume via Signals
- POST /api/v1/executions/{execution_id}/resume
- POST /api/v1/executions/{execution_id}/cancel
- POST /api/v1/executions/{execution_id}/retry
"""
from flask import request, jsonify
from app.controllers.api.v1.executions import bp
from app.models.execution import WorkflowExecution, ExecutionStatus
from app.temporal.client import get_temporal_client
import asyncio


@bp.route('/<execution_id>/resume', methods=['POST'])
def resume_execution(execution_id):
    """
    Retoma execução após needs_review (preflight fix).

    Body (opcional):
        {
            "data": {...}  // Dados adicionais para retomada
        }

    Returns:
        {'status': 'signal_sent'}
    """
    execution = WorkflowExecution.query.get_or_404(execution_id)

    if execution.status != ExecutionStatus.NEEDS_REVIEW.value:
        return jsonify({
            'error': f'Cannot resume - execution is {execution.status}, expected needs_review'
        }), 400

    # Enviar signal para Temporal
    if execution.temporal_workflow_id:
        try:
            client = asyncio.run(get_temporal_client())
            handle = client.get_workflow_handle(execution.temporal_workflow_id)

            data = request.json or {}
            asyncio.run(handle.signal('resume_after_review', data))

            return jsonify({'status': 'signal_sent'}), 200
        except Exception as e:
            return jsonify({'error': f'Failed to send signal: {str(e)}'}), 500
    else:
        return jsonify({'error': 'Execution not running in Temporal'}), 400


@bp.route('/<execution_id>/cancel', methods=['POST'])
def cancel_execution(execution_id):
    """
    Cancela execução em andamento.

    Body (opcional):
        {
            "reason": "User requested cancellation"
        }

    Returns:
        {'status': 'signal_sent'} ou {'status': 'execution_canceled'}
    """
    execution = WorkflowExecution.query.get_or_404(execution_id)

    if execution.status in [ExecutionStatus.COMPLETED.value, ExecutionStatus.FAILED.value, ExecutionStatus.CANCELED.value]:
        return jsonify({
            'error': f'Cannot cancel - execution already {execution.status}'
        }), 400

    # Enviar signal para Temporal
    if execution.temporal_workflow_id:
        try:
            client = asyncio.run(get_temporal_client())
            handle = client.get_workflow_handle(execution.temporal_workflow_id)

            reason = request.json.get('reason', 'User requested') if request.json else 'User requested'
            asyncio.run(handle.signal('cancel', {'reason': reason}))

            return jsonify({'status': 'signal_sent'}), 200
        except Exception as e:
            return jsonify({'error': f'Failed to send signal: {str(e)}'}), 500
    else:
        # Execução síncrona - marcar como canceled diretamente
        execution.status = ExecutionStatus.CANCELED.value
        from app.database import db
        db.session.commit()
        return jsonify({'status': 'execution_canceled'}), 200


@bp.route('/<execution_id>/retry', methods=['POST'])
def retry_execution(execution_id):
    """
    Reexecuta um workflow (cria nova execução).

    Body (opcional):
        {
            "trigger_data": {...},  // Sobrescrever dados do trigger
            "dry_run": false,        // Modo dry-run (pula delivery/signature)
            "until_phase": "render"  // Para após fase específica (preflight, trigger, render, save, delivery, signature)
        }

    Returns:
        {'execution_id': 'uuid', 'status': 'queued'}
    """
    original_execution = WorkflowExecution.query.get_or_404(execution_id)

    # Criar nova execução com mesmo workflow e trigger data
    from app.engine.engine import Engine
    from app.database import db

    request_data = request.json or {}
    trigger_data = request_data.get('trigger_data', original_execution.trigger_data)
    dry_run = request_data.get('dry_run', False)
    until_phase = request_data.get('until_phase')

    new_execution = WorkflowExecution(
        workflow_id=original_execution.workflow_id,
        trigger_type=original_execution.trigger_type,
        trigger_data=trigger_data,
        status=ExecutionStatus.QUEUED.value
    )

    db.session.add(new_execution)
    db.session.commit()

    # Iniciar execução
    try:
        asyncio.run(Engine.run(
            workflow_id=str(original_execution.workflow_id),
            trigger_data=trigger_data,
            execution_id=str(new_execution.id),
            dry_run=dry_run,
            until_phase=until_phase,
        ))
    except Exception as e:
        return jsonify({'error': f'Failed to start execution: {str(e)}'}), 500

    return jsonify({
        'execution_id': str(new_execution.id),
        'status': 'queued'
    }), 201
