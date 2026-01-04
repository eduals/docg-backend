"""
Flow Versions API - Routes for managing flow versions

Endpoints:
- GET /api/v1/flows/:flow_id/versions - List versions
- POST /api/v1/flows/:flow_id/versions - Create version
- GET /api/v1/flows/:flow_id/versions/:version_id - Get version details
- PUT /api/v1/flows/:flow_id/versions/:version_id - Update version
- DELETE /api/v1/flows/:flow_id/versions/:version_id - Delete version
- POST /api/v1/flows/:flow_id/versions/:version_id/lock - Lock version
"""

from flask import Blueprint, request, jsonify
from uuid import UUID, uuid4
from datetime import datetime
import logging

from app.database import db
from app.models.flow import Flow, FlowVersion, FlowVersionState

logger = logging.getLogger(__name__)

flow_versions_bp = Blueprint('flow_versions', __name__, url_prefix='/api/v1/flows')


@flow_versions_bp.route('/<flow_id>/versions', methods=['GET'])
def list_versions(flow_id):
    """List all versions for a flow."""
    try:
        flow = db.session.get(Flow, UUID(flow_id))
        if not flow:
            return jsonify({'error': 'Flow not found'}), 404

        versions = FlowVersion.query.filter_by(flow_id=flow.id).order_by(FlowVersion.version_number.desc()).all()

        return jsonify({
            'versions': [_serialize_version(v) for v in versions],
            'count': len(versions)
        }), 200

    except Exception as e:
        logger.error(f"Error listing versions: {e}")
        return jsonify({'error': str(e)}), 500


@flow_versions_bp.route('/<flow_id>/versions', methods=['POST'])
def create_version(flow_id):
    """
    Create a new version (draft).

    Body:
        {
            "trigger": {...},
            "definition": {"steps": [...]}
        }
    """
    try:
        flow = db.session.get(Flow, UUID(flow_id))
        if not flow:
            return jsonify({'error': 'Flow not found'}), 404

        data = request.get_json() or {}

        # Get next version number
        last_version = FlowVersion.query.filter_by(flow_id=flow.id).order_by(FlowVersion.version_number.desc()).first()
        next_version_number = (last_version.version_number + 1) if last_version else 1

        version = FlowVersion(
            id=uuid4(),
            flow_id=flow.id,
            version_number=next_version_number,
            state=FlowVersionState.DRAFT,
            trigger=data.get('trigger'),
            definition=data.get('definition', {'steps': []}),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        db.session.add(version)
        db.session.commit()

        logger.info(f"Created version: {version.id} (v{version.version_number}) for flow: {flow_id}")

        return jsonify(_serialize_version(version)), 201

    except Exception as e:
        logger.error(f"Error creating version: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@flow_versions_bp.route('/<flow_id>/versions/<version_id>', methods=['GET'])
def get_version(flow_id, version_id):
    """Get version details."""
    try:
        version = db.session.get(FlowVersion, UUID(version_id))
        if not version or str(version.flow_id) != flow_id:
            return jsonify({'error': 'Version not found'}), 404

        return jsonify(_serialize_version(version, include_full_definition=True)), 200

    except Exception as e:
        logger.error(f"Error getting version: {e}")
        return jsonify({'error': str(e)}), 500


@flow_versions_bp.route('/<flow_id>/versions/<version_id>', methods=['PUT'])
def update_version(flow_id, version_id):
    """
    Update version (only if DRAFT).

    Body:
        {
            "trigger": {...},
            "definition": {"steps": [...]}
        }
    """
    try:
        version = db.session.get(FlowVersion, UUID(version_id))
        if not version or str(version.flow_id) != flow_id:
            return jsonify({'error': 'Version not found'}), 404

        if version.state != FlowVersionState.DRAFT:
            return jsonify({'error': 'Cannot update locked version'}), 400

        data = request.get_json()

        # Update fields
        if 'trigger' in data:
            version.trigger = data['trigger']
        if 'definition' in data:
            version.definition = data['definition']

        version.updated_at = datetime.utcnow()

        db.session.commit()

        logger.info(f"Updated version: {version.id}")

        return jsonify(_serialize_version(version)), 200

    except Exception as e:
        logger.error(f"Error updating version: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@flow_versions_bp.route('/<flow_id>/versions/<version_id>', methods=['DELETE'])
def delete_version(flow_id, version_id):
    """Delete a version (only if DRAFT and not published)."""
    try:
        version = db.session.get(FlowVersion, UUID(version_id))
        if not version or str(version.flow_id) != flow_id:
            return jsonify({'error': 'Version not found'}), 404

        # Check if it's the published version
        flow = db.session.get(Flow, version.flow_id)
        if flow.published_version_id == version.id:
            return jsonify({'error': 'Cannot delete published version'}), 400

        if version.state != FlowVersionState.DRAFT:
            return jsonify({'error': 'Cannot delete locked version'}), 400

        db.session.delete(version)
        db.session.commit()

        logger.info(f"Deleted version: {version_id}")

        return jsonify({'message': 'Version deleted successfully'}), 200

    except Exception as e:
        logger.error(f"Error deleting version: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@flow_versions_bp.route('/<flow_id>/versions/<version_id>/lock', methods=['POST'])
def lock_version(flow_id, version_id):
    """Lock a version (makes it immutable)."""
    try:
        version = db.session.get(FlowVersion, UUID(version_id))
        if not version or str(version.flow_id) != flow_id:
            return jsonify({'error': 'Version not found'}), 404

        if version.state == FlowVersionState.LOCKED:
            return jsonify({'error': 'Version already locked'}), 400

        version.state = FlowVersionState.LOCKED
        version.updated_at = datetime.utcnow()

        db.session.commit()

        logger.info(f"Locked version: {version.id}")

        return jsonify(_serialize_version(version)), 200

    except Exception as e:
        logger.error(f"Error locking version: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


def _serialize_version(version: FlowVersion, include_full_definition: bool = False) -> dict:
    """Serialize flow version to dict."""
    data = {
        'id': str(version.id),
        'flow_id': str(version.flow_id),
        'version_number': version.version_number,
        'state': version.state.value,
        'created_at': version.created_at.isoformat() if version.created_at else None,
        'updated_at': version.updated_at.isoformat() if version.updated_at else None,
    }

    if include_full_definition:
        data['trigger'] = version.trigger
        data['definition'] = version.definition

    return data
