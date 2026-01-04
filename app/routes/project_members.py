"""
Project Members API - Routes for managing project members and roles

Endpoints:
- GET /api/v1/projects/:project_id/members - List members
- POST /api/v1/projects/:project_id/members - Add member
- GET /api/v1/projects/:project_id/members/:member_id - Get member
- PUT /api/v1/projects/:project_id/members/:member_id - Update member role
- DELETE /api/v1/projects/:project_id/members/:member_id - Remove member
- GET /api/v1/projects/:project_id/roles - List available roles
- POST /api/v1/projects/:project_id/roles - Create custom role
"""

from flask import Blueprint, request, jsonify, g
from uuid import UUID, uuid4
from datetime import datetime
import logging

from app.database import db
from app.models.permissions import ProjectMember, ProjectRole, DefaultProjectRole, ROLE_PERMISSIONS
from app.utils.auth import require_jwt_auth

logger = logging.getLogger(__name__)

project_members_bp = Blueprint('project_members', __name__, url_prefix='/api/v1/projects')


@project_members_bp.route('/<project_id>/members', methods=['GET'])
def list_members(project_id):
    """List all members of a project."""
    try:
        members = ProjectMember.query.filter_by(project_id=UUID(project_id)).all()

        return jsonify({
            'members': [_serialize_member(m) for m in members],
            'count': len(members)
        }), 200

    except Exception as e:
        logger.error(f"Error listing members: {e}")
        return jsonify({'error': str(e)}), 500


@project_members_bp.route('/<project_id>/members', methods=['POST'])
def add_member(project_id):
    """
    Add a member to a project.

    Body:
        {
            "user_id": "uuid",
            "project_role_id": "uuid"
        }
    """
    data = request.get_json()

    if not data.get('user_id') or not data.get('project_role_id'):
        return jsonify({'error': 'user_id and project_role_id are required'}), 400

    try:
        # Check if member already exists
        existing = ProjectMember.query.filter_by(
            project_id=UUID(project_id),
            user_id=UUID(data['user_id'])
        ).first()

        if existing:
            return jsonify({'error': 'User is already a member'}), 400

        member = ProjectMember(
            id=uuid4(),
            project_id=UUID(project_id),
            user_id=UUID(data['user_id']),
            project_role_id=UUID(data['project_role_id']),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        db.session.add(member)
        db.session.commit()

        logger.info(f"Added member: {data['user_id']} to project: {project_id}")

        return jsonify(_serialize_member(member)), 201

    except Exception as e:
        logger.error(f"Error adding member: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@project_members_bp.route('/<project_id>/members/<member_id>', methods=['GET'])
def get_member(project_id, member_id):
    """Get member details."""
    try:
        member = db.session.get(ProjectMember, UUID(member_id))
        if not member or str(member.project_id) != project_id:
            return jsonify({'error': 'Member not found'}), 404

        return jsonify(_serialize_member(member, include_user=True)), 200

    except Exception as e:
        logger.error(f"Error getting member: {e}")
        return jsonify({'error': str(e)}), 500


@project_members_bp.route('/<project_id>/members/<member_id>', methods=['PUT'])
def update_member(project_id, member_id):
    """
    Update member role.

    Body:
        {
            "project_role_id": "uuid"
        }
    """
    try:
        member = db.session.get(ProjectMember, UUID(member_id))
        if not member or str(member.project_id) != project_id:
            return jsonify({'error': 'Member not found'}), 404

        data = request.get_json()

        if 'project_role_id' in data:
            member.project_role_id = UUID(data['project_role_id'])

        member.updated_at = datetime.utcnow()

        db.session.commit()

        logger.info(f"Updated member: {member_id}")

        return jsonify(_serialize_member(member)), 200

    except Exception as e:
        logger.error(f"Error updating member: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@project_members_bp.route('/<project_id>/members/<member_id>', methods=['DELETE'])
def remove_member(project_id, member_id):
    """Remove a member from a project."""
    try:
        member = db.session.get(ProjectMember, UUID(member_id))
        if not member or str(member.project_id) != project_id:
            return jsonify({'error': 'Member not found'}), 404

        db.session.delete(member)
        db.session.commit()

        logger.info(f"Removed member: {member_id} from project: {project_id}")

        return jsonify({'message': 'Member removed successfully'}), 200

    except Exception as e:
        logger.error(f"Error removing member: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@project_members_bp.route('/<project_id>/roles', methods=['GET'])
def list_roles(project_id):
    """List all available roles for a project (default + custom)."""
    try:
        roles = ProjectRole.query.filter_by(project_id=UUID(project_id)).all()

        return jsonify({
            'roles': [_serialize_role(r) for r in roles],
            'count': len(roles)
        }), 200

    except Exception as e:
        logger.error(f"Error listing roles: {e}")
        return jsonify({'error': str(e)}), 500


@project_members_bp.route('/<project_id>/roles', methods=['POST'])
def create_custom_role(project_id):
    """
    Create a custom role.

    Body:
        {
            "name": "Custom Role",
            "permissions": ["READ_FLOW", "EXECUTE_FLOW", ...]
        }
    """
    data = request.get_json()

    if not data.get('name') or not data.get('permissions'):
        return jsonify({'error': 'name and permissions are required'}), 400

    try:
        role = ProjectRole(
            id=uuid4(),
            project_id=UUID(project_id),
            name=data['name'],
            type='CUSTOM',
            permissions=data['permissions'],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        db.session.add(role)
        db.session.commit()

        logger.info(f"Created custom role: {role.id} - {role.name}")

        return jsonify(_serialize_role(role)), 201

    except Exception as e:
        logger.error(f"Error creating role: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


def _serialize_member(member: ProjectMember, include_user: bool = False) -> dict:
    """Serialize project member to dict."""
    data = {
        'id': str(member.id),
        'project_id': str(member.project_id),
        'user_id': str(member.user_id),
        'project_role_id': str(member.project_role_id),
        'created_at': member.created_at.isoformat() if member.created_at else None,
        'updated_at': member.updated_at.isoformat() if member.updated_at else None,
    }

    if include_user:
        # Include user details
        from app.models.organization import User
        user = db.session.get(User, member.user_id)
        if user:
            data['user'] = {
                'id': str(user.id),
                'email': user.email,
                'name': user.name,
            }

        # Include role details
        role = db.session.get(ProjectRole, member.project_role_id)
        if role:
            data['role'] = _serialize_role(role)

    return data


def _serialize_role(role: ProjectRole) -> dict:
    """Serialize project role to dict."""
    return {
        'id': str(role.id),
        'project_id': str(role.project_id) if role.project_id else None,
        'name': role.name,
        'type': role.type,
        'permissions': role.permissions if role.permissions else [],
        'created_at': role.created_at.isoformat() if role.created_at else None,
        'updated_at': role.updated_at.isoformat() if role.updated_at else None,
    }


# ActivePieces-specific endpoint
# This endpoint uses a different blueprint prefix
from flask import Blueprint as BP
project_members_role_bp = BP('project_members_role', __name__, url_prefix='/api/v1')


@project_members_role_bp.route('/project-members/role', methods=['GET'])
@require_jwt_auth
def get_current_user_role():
    """
    Get current user's role in a specific project.
    ActivePieces-compatible endpoint.

    Query Params:
        projectId: UUID of the project

    Returns:
        ProjectRole | null
    """
    project_id = request.args.get('projectId')

    if not project_id:
        return jsonify({'error': 'projectId query parameter is required'}), 400

    user_id = g.user_id

    if not user_id:
        return jsonify({'error': 'User not authenticated'}), 401

    try:
        # Find user's membership in the project
        membership = ProjectMember.query.filter_by(
            project_id=UUID(project_id),
            user_id=UUID(user_id)
        ).first()

        if not membership:
            # User is not a member of this project
            return jsonify(None), 200

        # Get the role details
        role = ProjectRole.query.filter_by(id=membership.project_role_id).first()

        if not role:
            return jsonify(None), 200

        return jsonify(_serialize_role(role)), 200

    except Exception as e:
        logger.error(f"Error getting user role: {e}")
        return jsonify({'error': str(e)}), 500
