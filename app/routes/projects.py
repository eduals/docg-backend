"""
Projects API - Routes for managing projects

Endpoints:
- GET /api/v1/projects - List projects
- POST /api/v1/projects - Create project
- GET /api/v1/projects/:id - Get project details
- PUT /api/v1/projects/:id - Update project
- DELETE /api/v1/projects/:id - Delete project
"""

from flask import Blueprint, request, jsonify
from uuid import UUID, uuid4
from datetime import datetime
import logging

from app.database import db
from app.models.platform import Project

logger = logging.getLogger(__name__)

projects_bp = Blueprint('projects', __name__, url_prefix='/api/v1/projects')


@projects_bp.route('', methods=['GET'])
def list_projects():
    """
    List all projects for a platform.

    Query params:
        platform_id: Filter by platform
    """
    platform_id = request.args.get('platform_id')

    query = Project.query

    if platform_id:
        query = query.filter_by(platform_id=UUID(platform_id))

    projects = query.order_by(Project.created_at.desc()).all()

    return jsonify({
        'projects': [_serialize_project(p) for p in projects],
        'count': len(projects)
    }), 200


@projects_bp.route('', methods=['POST'])
def create_project():
    """
    Create a new project.

    Body:
        {
            "platform_id": "uuid",
            "name": "My Project",
            "is_private": false
        }
    """
    data = request.get_json()

    # Validate required fields
    if not data.get('platform_id') or not data.get('name'):
        return jsonify({'error': 'platform_id and name are required'}), 400

    try:
        project = Project(
            id=uuid4(),
            platform_id=UUID(data['platform_id']),
            name=data['name'],
            is_private=data.get('is_private', False),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        db.session.add(project)
        db.session.commit()

        logger.info(f"Created project: {project.id} - {project.name}")

        return jsonify(_serialize_project(project)), 201

    except Exception as e:
        logger.error(f"Error creating project: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@projects_bp.route('/<project_id>', methods=['GET'])
def get_project(project_id):
    """Get project details."""
    try:
        project = db.session.get(Project, UUID(project_id))
        if not project:
            return jsonify({'error': 'Project not found'}), 404

        return jsonify(_serialize_project(project, include_stats=True)), 200

    except Exception as e:
        logger.error(f"Error getting project: {e}")
        return jsonify({'error': str(e)}), 500


@projects_bp.route('/<project_id>', methods=['PUT'])
def update_project(project_id):
    """
    Update project.

    Body:
        {
            "name": "Updated name",
            "is_private": true
        }
    """
    try:
        project = db.session.get(Project, UUID(project_id))
        if not project:
            return jsonify({'error': 'Project not found'}), 404

        data = request.get_json()

        # Update fields
        if 'name' in data:
            project.name = data['name']
        if 'is_private' in data:
            project.is_private = data['is_private']

        project.updated_at = datetime.utcnow()

        db.session.commit()

        logger.info(f"Updated project: {project.id}")

        return jsonify(_serialize_project(project)), 200

    except Exception as e:
        logger.error(f"Error updating project: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@projects_bp.route('/<project_id>', methods=['DELETE'])
def delete_project(project_id):
    """Delete a project."""
    try:
        project = db.session.get(Project, UUID(project_id))
        if not project:
            return jsonify({'error': 'Project not found'}), 404

        db.session.delete(project)
        db.session.commit()

        logger.info(f"Deleted project: {project_id}")

        return jsonify({'message': 'Project deleted successfully'}), 200

    except Exception as e:
        logger.error(f"Error deleting project: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


def _serialize_project(project: Project, include_stats: bool = False) -> dict:
    """Serialize project to dict."""
    data = {
        'id': str(project.id),
        'platform_id': str(project.platform_id),
        'name': project.name,
        'is_private': project.is_private,
        'created_at': project.created_at.isoformat() if project.created_at else None,
        'updated_at': project.updated_at.isoformat() if project.updated_at else None,
    }

    if include_stats:
        # Add flow count
        from app.models.flow import Flow
        flow_count = Flow.query.filter_by(project_id=project.id).count()
        data['flow_count'] = flow_count

    return data
