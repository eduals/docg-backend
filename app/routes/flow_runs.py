"""
Flow Runs API - Routes for viewing and managing flow executions

Endpoints:
- GET /api/v1/flow-runs - List flow runs
- GET /api/v1/flow-runs/:id - Get run details
- GET /api/v1/flow-runs/:id/logs - Get run logs
- POST /api/v1/flow-runs/:id/cancel - Cancel run
"""

from flask import Blueprint, request, jsonify
from uuid import UUID
import logging

from app.database import db
from app.models.flow import FlowRun, FlowRunLog, FlowRunStatus
from app.services.flow_execution_service import get_flow_execution_service

logger = logging.getLogger(__name__)

flow_runs_bp = Blueprint('flow_runs', __name__, url_prefix='/api/v1/flow-runs')


@flow_runs_bp.route('', methods=['GET'])
def list_flow_runs():
    """
    List flow runs.

    Query params:
        flow_id: Filter by flow
        status: Filter by status
        limit: Max results (default: 50)
        offset: Pagination offset
    """
    flow_id = request.args.get('flow_id')
    status = request.args.get('status')
    limit = int(request.args.get('limit', 50))
    offset = int(request.args.get('offset', 0))

    query = FlowRun.query

    if flow_id:
        query = query.filter_by(flow_id=UUID(flow_id))

    if status:
        query = query.filter_by(status=FlowRunStatus(status))

    total = query.count()
    runs = query.order_by(FlowRun.created_at.desc()).limit(limit).offset(offset).all()

    return jsonify({
        'runs': [_serialize_run(r) for r in runs],
        'total': total,
        'limit': limit,
        'offset': offset
    }), 200


@flow_runs_bp.route('/<run_id>', methods=['GET'])
def get_flow_run(run_id):
    """Get flow run details."""
    try:
        run = db.session.get(FlowRun, UUID(run_id))
        if not run:
            return jsonify({'error': 'Flow run not found'}), 404

        return jsonify(_serialize_run(run, include_details=True)), 200

    except Exception as e:
        logger.error(f"Error getting flow run: {e}")
        return jsonify({'error': str(e)}), 500


@flow_runs_bp.route('/<run_id>/logs', methods=['GET'])
def get_flow_run_logs(run_id):
    """
    Get flow run logs.

    Query params:
        level: Filter by level (ok, info, warn, error)
        domain: Filter by domain (trigger, step, execution, etc)
        limit: Max results (default: 100)
    """
    try:
        run = db.session.get(FlowRun, UUID(run_id))
        if not run:
            return jsonify({'error': 'Flow run not found'}), 404

        level = request.args.get('level')
        domain = request.args.get('domain')
        limit = int(request.args.get('limit', 100))

        query = FlowRunLog.query.filter_by(flow_run_id=run.id)

        if level:
            query = query.filter_by(level=level)

        if domain:
            query = query.filter_by(domain=domain)

        logs = query.order_by(FlowRunLog.timestamp.asc()).limit(limit).all()

        return jsonify({
            'logs': [_serialize_log(log) for log in logs],
            'count': len(logs)
        }), 200

    except Exception as e:
        logger.error(f"Error getting flow run logs: {e}")
        return jsonify({'error': str(e)}), 500


@flow_runs_bp.route('/<run_id>/cancel', methods=['POST'])
async def cancel_flow_run(run_id):
    """Cancel a running flow."""
    try:
        run = db.session.get(FlowRun, UUID(run_id))
        if not run:
            return jsonify({'error': 'Flow run not found'}), 404

        if run.status not in [FlowRunStatus.QUEUED, FlowRunStatus.RUNNING]:
            return jsonify({'error': f'Cannot cancel run with status: {run.status.value}'}), 400

        # Get workflow ID (assuming it's stored or we can derive it)
        # For now, we'll update the run status directly
        run.status = FlowRunStatus.CANCELED
        run.error_message = 'Canceled by user'
        db.session.commit()

        logger.info(f"Canceled flow run: {run_id}")

        return jsonify(_serialize_run(run)), 200

    except Exception as e:
        logger.error(f"Error canceling flow run: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


def _serialize_run(run: FlowRun, include_details: bool = False) -> dict:
    """Serialize flow run to dict."""
    data = {
        'id': str(run.id),
        'flow_id': str(run.flow_id),
        'flow_version_id': str(run.flow_version_id),
        'status': run.status.value,
        'progress': run.progress,
        'current_step': run.current_step,
        'error_message': run.error_message,
        'started_at': run.started_at.isoformat() if run.started_at else None,
        'completed_at': run.completed_at.isoformat() if run.completed_at else None,
        'created_at': run.created_at.isoformat() if run.created_at else None,
    }

    if include_details:
        data['trigger_data'] = run.trigger_data
        # Include flow name
        flow = db.session.get('Flow', run.flow_id)
        if flow:
            data['flow_name'] = flow.name

    return data


def _serialize_log(log: FlowRunLog) -> dict:
    """Serialize flow run log to dict."""
    return {
        'id': str(log.id),
        'timestamp': log.timestamp.isoformat() if log.timestamp else None,
        'level': log.level,
        'domain': log.domain,
        'message': log.message,
    }
