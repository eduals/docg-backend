"""
Folders API - Routes for organizing flows in folders

Endpoints:
- GET /api/v1/folders - List folders
- POST /api/v1/folders - Create folder
- GET /api/v1/folders/:id - Get folder details
- PUT /api/v1/folders/:id - Update folder
- DELETE /api/v1/folders/:id - Delete folder
"""

from flask import Blueprint, request, jsonify
from uuid import UUID, uuid4
from datetime import datetime
import logging

from app.database import db
from app.models.platform import Folder

logger = logging.getLogger(__name__)

folders_bp = Blueprint('folders', __name__, url_prefix='/api/v1/folders')


@folders_bp.route('', methods=['GET'])
def list_folders():
    """
    List all folders for a project.

    Query params:
        project_id: Filter by project (required)
    """
    project_id = request.args.get('project_id')

    if not project_id:
        return jsonify({'error': 'project_id is required'}), 400

    try:
        folders = Folder.query.filter_by(project_id=UUID(project_id)).order_by(Folder.name).all()

        return jsonify({
            'folders': [_serialize_folder(f) for f in folders],
            'count': len(folders)
        }), 200

    except Exception as e:
        logger.error(f"Error listing folders: {e}")
        return jsonify({'error': str(e)}), 500


@folders_bp.route('', methods=['POST'])
def create_folder():
    """
    Create a new folder.

    Body:
        {
            "project_id": "uuid",
            "name": "My Folder"
        }
    """
    data = request.get_json()

    # Validate required fields
    if not data.get('project_id') or not data.get('name'):
        return jsonify({'error': 'project_id and name are required'}), 400

    try:
        folder = Folder(
            id=uuid4(),
            project_id=UUID(data['project_id']),
            name=data['name'],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        db.session.add(folder)
        db.session.commit()

        logger.info(f"Created folder: {folder.id} - {folder.name}")

        return jsonify(_serialize_folder(folder)), 201

    except Exception as e:
        logger.error(f"Error creating folder: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@folders_bp.route('/<folder_id>', methods=['GET'])
def get_folder(folder_id):
    """Get folder details including flow count."""
    try:
        folder = db.session.get(Folder, UUID(folder_id))
        if not folder:
            return jsonify({'error': 'Folder not found'}), 404

        return jsonify(_serialize_folder(folder, include_stats=True)), 200

    except Exception as e:
        logger.error(f"Error getting folder: {e}")
        return jsonify({'error': str(e)}), 500


@folders_bp.route('/<folder_id>', methods=['PUT'])
def update_folder(folder_id):
    """
    Update folder.

    Body:
        {
            "name": "Updated name"
        }
    """
    try:
        folder = db.session.get(Folder, UUID(folder_id))
        if not folder:
            return jsonify({'error': 'Folder not found'}), 404

        data = request.get_json()

        # Update fields
        if 'name' in data:
            folder.name = data['name']

        folder.updated_at = datetime.utcnow()

        db.session.commit()

        logger.info(f"Updated folder: {folder.id}")

        return jsonify(_serialize_folder(folder)), 200

    except Exception as e:
        logger.error(f"Error updating folder: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@folders_bp.route('/<folder_id>', methods=['DELETE'])
def delete_folder(folder_id):
    """Delete a folder (flows will become un-foldered)."""
    try:
        folder = db.session.get(Folder, UUID(folder_id))
        if not folder:
            return jsonify({'error': 'Folder not found'}), 404

        # Set flows' folder_id to NULL
        from app.models.flow import Flow
        Flow.query.filter_by(folder_id=folder.id).update({'folder_id': None})

        db.session.delete(folder)
        db.session.commit()

        logger.info(f"Deleted folder: {folder_id}")

        return jsonify({'message': 'Folder deleted successfully'}), 200

    except Exception as e:
        logger.error(f"Error deleting folder: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


def _serialize_folder(folder: Folder, include_stats: bool = False) -> dict:
    """Serialize folder to dict."""
    data = {
        'id': str(folder.id),
        'project_id': str(folder.project_id),
        'name': folder.name,
        'created_at': folder.created_at.isoformat() if folder.created_at else None,
        'updated_at': folder.updated_at.isoformat() if folder.updated_at else None,
    }

    if include_stats:
        # Add flow count
        from app.models.flow import Flow
        flow_count = Flow.query.filter_by(folder_id=folder.id).count()
        data['flow_count'] = flow_count

    return data
