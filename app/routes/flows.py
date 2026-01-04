"""
Flows API - Routes for managing flows (workflows)

Endpoints:
- GET /api/v1/flows - List flows
- POST /api/v1/flows - Create flow
- GET /api/v1/flows/:id - Get flow details
- PUT /api/v1/flows/:id - Update flow
- DELETE /api/v1/flows/:id - Delete flow
- POST /api/v1/flows/:id/execute - Execute flow
"""

from flask import Blueprint, request, jsonify
from uuid import UUID, uuid4
from datetime import datetime
import logging

from app.database import db
from app.models.flow import Flow, FlowVersion, FlowStatus, FlowVersionState
from app.services.flow_execution_service import get_flow_execution_service

logger = logging.getLogger(__name__)

flows_bp = Blueprint('flows', __name__, url_prefix='/api/v1/flows')


@flows_bp.route('', methods=['GET'])
def list_flows():
    """
    List all flows for a project.

    Query params:
        project_id: Filter by project
        status: Filter by status (ENABLED, DISABLED)
    """
    project_id = request.args.get('project_id')
    status = request.args.get('status')

    query = Flow.query

    if project_id:
        query = query.filter_by(project_id=UUID(project_id))

    if status:
        query = query.filter_by(status=status)

    flows = query.order_by(Flow.created_at.desc()).all()

    return jsonify({
        'flows': [_serialize_flow(f) for f in flows],
        'count': len(flows)
    }), 200


@flows_bp.route('', methods=['POST'])
def create_flow():
    """
    Create a new flow.

    Body:
        {
            "project_id": "uuid",
            "name": "My Flow",
            "description": "Flow description",
            "folder_id": "uuid" (optional)
        }
    """
    data = request.get_json()

    # Validate required fields
    if not data.get('project_id') or not data.get('name'):
        return jsonify({'error': 'project_id and name are required'}), 400

    try:
        # Create flow
        flow = Flow(
            id=uuid4(),
            project_id=UUID(data['project_id']),
            name=data['name'],
            description=data.get('description'),
            folder_id=UUID(data['folder_id']) if data.get('folder_id') else None,
            status=FlowStatus.DISABLED,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        db.session.add(flow)

        # Create initial draft version
        version = FlowVersion(
            id=uuid4(),
            flow_id=flow.id,
            version_number=1,
            state=FlowVersionState.DRAFT,
            trigger=None,
            definition={'steps': []},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        db.session.add(version)
        db.session.commit()

        logger.info(f"Created flow: {flow.id} - {flow.name}")

        return jsonify(_serialize_flow(flow)), 201

    except Exception as e:
        logger.error(f"Error creating flow: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@flows_bp.route('/<flow_id>', methods=['GET'])
def get_flow(flow_id):
    """Get flow details including current version."""
    try:
        flow = db.session.get(Flow, UUID(flow_id))
        if not flow:
            return jsonify({'error': 'Flow not found'}), 404

        return jsonify(_serialize_flow(flow, include_version=True)), 200

    except Exception as e:
        logger.error(f"Error getting flow: {e}")
        return jsonify({'error': str(e)}), 500


@flows_bp.route('/<flow_id>', methods=['PUT'])
def update_flow(flow_id):
    """
    Update flow.

    Body:
        {
            "name": "Updated name",
            "description": "Updated description",
            "folder_id": "uuid"
        }
    """
    try:
        flow = db.session.get(Flow, UUID(flow_id))
        if not flow:
            return jsonify({'error': 'Flow not found'}), 404

        data = request.get_json()

        # Update fields
        if 'name' in data:
            flow.name = data['name']
        if 'description' in data:
            flow.description = data['description']
        if 'folder_id' in data:
            flow.folder_id = UUID(data['folder_id']) if data['folder_id'] else None

        flow.updated_at = datetime.utcnow()

        db.session.commit()

        logger.info(f"Updated flow: {flow.id}")

        return jsonify(_serialize_flow(flow)), 200

    except Exception as e:
        logger.error(f"Error updating flow: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@flows_bp.route('/<flow_id>', methods=['DELETE'])
def delete_flow(flow_id):
    """Delete a flow."""
    try:
        flow = db.session.get(Flow, UUID(flow_id))
        if not flow:
            return jsonify({'error': 'Flow not found'}), 404

        db.session.delete(flow)
        db.session.commit()

        logger.info(f"Deleted flow: {flow_id}")

        return jsonify({'message': 'Flow deleted successfully'}), 200

    except Exception as e:
        logger.error(f"Error deleting flow: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@flows_bp.route('/<flow_id>/publish', methods=['POST'])
def publish_flow(flow_id):
    """
    Publish a flow (enable it for execution).

    Body:
        {
            "version_id": "uuid"  # Version to publish
        }
    """
    try:
        flow = db.session.get(Flow, UUID(flow_id))
        if not flow:
            return jsonify({'error': 'Flow not found'}), 404

        data = request.get_json()
        version_id = data.get('version_id')

        if not version_id:
            return jsonify({'error': 'version_id is required'}), 400

        version = db.session.get(FlowVersion, UUID(version_id))
        if not version or version.flow_id != flow.id:
            return jsonify({'error': 'Version not found'}), 404

        # Lock version
        version.state = FlowVersionState.LOCKED
        version.updated_at = datetime.utcnow()

        # Set as published version
        flow.published_version_id = version.id
        flow.status = FlowStatus.ENABLED
        flow.updated_at = datetime.utcnow()

        db.session.commit()

        logger.info(f"Published flow: {flow.id} with version: {version.id}")

        return jsonify(_serialize_flow(flow)), 200

    except Exception as e:
        logger.error(f"Error publishing flow: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@flows_bp.route('/<flow_id>/execute', methods=['POST'])
async def execute_flow(flow_id):
    """
    Execute a flow.

    Body:
        {
            "trigger_data": {...}  # Data to pass to trigger
        }
    """
    try:
        flow = db.session.get(Flow, UUID(flow_id))
        if not flow:
            return jsonify({'error': 'Flow not found'}), 404

        if flow.status != FlowStatus.ENABLED:
            return jsonify({'error': 'Flow is not enabled'}), 400

        data = request.get_json() or {}
        trigger_data = data.get('trigger_data', {})

        # Start execution via Temporal
        service = get_flow_execution_service()
        workflow_id = await service.start_flow_execution(
            flow_id=flow_id,
            trigger_data=trigger_data,
            project_id=str(flow.project_id)
        )

        logger.info(f"Started execution for flow: {flow_id}, workflow: {workflow_id}")

        return jsonify({
            'workflow_id': workflow_id,
            'flow_id': flow_id,
            'status': 'started'
        }), 202

    except Exception as e:
        logger.error(f"Error executing flow: {e}")
        return jsonify({'error': str(e)}), 500


def _serialize_flow(flow: Flow, include_version: bool = False) -> dict:
    """Serialize flow to dict."""
    data = {
        'id': str(flow.id),
        'project_id': str(flow.project_id),
        'name': flow.name,
        'description': flow.description,
        'folder_id': str(flow.folder_id) if flow.folder_id else None,
        'status': flow.status.value,
        'published_version_id': str(flow.published_version_id) if flow.published_version_id else None,
        'created_at': flow.created_at.isoformat() if flow.created_at else None,
        'updated_at': flow.updated_at.isoformat() if flow.updated_at else None,
    }

    if include_version and flow.published_version_id:
        version = db.session.get(FlowVersion, flow.published_version_id)
        if version:
            data['published_version'] = {
                'id': str(version.id),
                'version_number': version.version_number,
                'state': version.state.value,
                'trigger': version.trigger,
                'definition': version.definition,
            }

    return data
