"""
Steps Controller - Endpoint para consultar steps de execução.

Feature 7: Steps Persistidos + Snapshots
GET /api/v1/executions/{execution_id}/steps
"""
from flask import jsonify
from app.controllers.api.v1.executions import bp
from app.models.execution_step import ExecutionStep
from app.models.execution import WorkflowExecution


@bp.route('/<execution_id>/steps', methods=['GET'])
def get_steps(execution_id):
    """
    Retorna todos os steps de uma execução, ordenados por posição.

    Returns:
        {
            'steps': [...]
        }
    """
    # Verificar se execução existe
    execution = WorkflowExecution.query.get_or_404(execution_id)

    # Buscar steps ordenados por posição
    steps = ExecutionStep.query.filter_by(
        execution_id=execution_id
    ).order_by(ExecutionStep.position).all()

    return jsonify({
        'steps': [step.to_dict(include_data=True) for step in steps]
    })
