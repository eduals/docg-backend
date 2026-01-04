"""
Trigger Events API - Routes for webhook triggers and event handling

Endpoints:
- POST /api/v1/webhooks/:flow_id - Receive webhook and trigger flow
- GET /api/v1/trigger-events - List trigger events
- GET /api/v1/trigger-events/:id - Get trigger event details
"""

from flask import Blueprint, request, jsonify
from uuid import UUID, uuid4
from datetime import datetime
import logging

from app.database import db
from app.models.flow import Flow, TriggerEvent
from app.services.flow_execution_service import get_flow_execution_service

logger = logging.getLogger(__name__)

trigger_events_bp = Blueprint('trigger_events', __name__, url_prefix='/api/v1')


@trigger_events_bp.route('/webhooks/<flow_id>', methods=['POST'])
async def receive_webhook(flow_id):
    """
    Receive webhook and trigger flow execution.

    Any POST to this endpoint will trigger the flow with the request body as trigger_data.
    """
    try:
        # Get flow
        flow = db.session.get(Flow, UUID(flow_id))
        if not flow:
            return jsonify({'error': 'Flow not found'}), 404

        if flow.status != 'ENABLED':
            return jsonify({'error': 'Flow is not enabled'}), 400

        # Get webhook payload
        trigger_data = request.get_json() or {}

        # Create trigger event
        event = TriggerEvent(
            id=uuid4(),
            flow_id=flow.id,
            source_type='WEBHOOK',
            payload=trigger_data,
            received_at=datetime.utcnow(),
        )
        db.session.add(event)
        db.session.commit()

        logger.info(f"Received webhook for flow: {flow_id}, event: {event.id}")

        # Start flow execution
        service = get_flow_execution_service()
        workflow_id = await service.start_flow_execution(
            flow_id=flow_id,
            trigger_data=trigger_data,
            project_id=str(flow.project_id)
        )

        logger.info(f"Started execution for webhook: {workflow_id}")

        return jsonify({
            'event_id': str(event.id),
            'workflow_id': workflow_id,
            'status': 'triggered'
        }), 202

    except Exception as e:
        logger.error(f"Error receiving webhook: {e}")
        return jsonify({'error': str(e)}), 500


@trigger_events_bp.route('/trigger-events', methods=['GET'])
def list_trigger_events():
    """
    List trigger events.

    Query params:
        flow_id: Filter by flow
        source_type: Filter by source type (WEBHOOK, SCHEDULE, MANUAL)
        limit: Max results (default: 50)
        offset: Pagination offset
    """
    flow_id = request.args.get('flow_id')
    source_type = request.args.get('source_type')
    limit = int(request.args.get('limit', 50))
    offset = int(request.args.get('offset', 0))

    query = TriggerEvent.query

    if flow_id:
        query = query.filter_by(flow_id=UUID(flow_id))

    if source_type:
        query = query.filter_by(source_type=source_type)

    total = query.count()
    events = query.order_by(TriggerEvent.received_at.desc()).limit(limit).offset(offset).all()

    return jsonify({
        'events': [_serialize_event(e) for e in events],
        'total': total,
        'limit': limit,
        'offset': offset
    }), 200


@trigger_events_bp.route('/trigger-events/<event_id>', methods=['GET'])
def get_trigger_event(event_id):
    """Get trigger event details."""
    try:
        event = db.session.get(TriggerEvent, UUID(event_id))
        if not event:
            return jsonify({'error': 'Trigger event not found'}), 404

        return jsonify(_serialize_event(event, include_payload=True)), 200

    except Exception as e:
        logger.error(f"Error getting trigger event: {e}")
        return jsonify({'error': str(e)}), 500


def _serialize_event(event: TriggerEvent, include_payload: bool = False) -> dict:
    """Serialize trigger event to dict."""
    data = {
        'id': str(event.id),
        'flow_id': str(event.flow_id),
        'source_type': event.source_type,
        'received_at': event.received_at.isoformat() if event.received_at else None,
    }

    if include_payload:
        data['payload'] = event.payload

    return data
