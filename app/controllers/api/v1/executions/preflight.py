"""
Preflight Controller - Endpoint para executar preflight check.

Feature 2: Preflight Real
- POST /api/v1/workflows/{workflow_id}/preflight
- GET /api/v1/executions/{execution_id}/preflight
"""
from flask import request, jsonify
from app.controllers.api.v1.executions import bp
from app.models.execution import WorkflowExecution
from app.models.workflow import Workflow
import asyncio


@bp.route('/<execution_id>/preflight', methods=['GET'])
def get_preflight_result(execution_id):
    """
    Retorna resultado do preflight check de uma execução.

    Returns:
        {
            'preflight_summary': {...} ou null
        }
    """
    execution = WorkflowExecution.query.get_or_404(execution_id)

    return jsonify({
        'preflight_summary': execution.preflight_summary
    })


# Endpoint alternativo para executar preflight antes de criar execução
from flask import Blueprint
preflight_bp = Blueprint('preflight', __name__, url_prefix='/api/v1/workflows')


@preflight_bp.route('/<workflow_id>/preflight', methods=['POST'])
def run_preflight(workflow_id):
    """
    Executa preflight check sem criar execução.

    Body:
        {
            "trigger_data": {...}  // Dados do trigger para validação
        }

    Returns:
        {
            'blocking_count': 0,
            'warning_count': 1,
            'groups': {...},
            'recommended_actions': [...]
        }
    """
    workflow = Workflow.query.get_or_404(workflow_id)

    trigger_data = request.json.get('trigger_data', {}) if request.json else {}

    # Executar preflight activity
    try:
        from app.temporal.activities.preflight import run_preflight_check

        result = asyncio.run(run_preflight_check(
            workflow_id=str(workflow.id),
            trigger_data=trigger_data
        ))

        return jsonify({
            'blocking_count': len(result.blocking),
            'warning_count': len(result.warnings),
            'groups': result.groups,
            'recommended_actions': [action.to_dict() for action in result.recommended_actions]
        }), 200
    except Exception as e:
        return jsonify({'error': f'Preflight check failed: {str(e)}'}), 500
