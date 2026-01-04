"""
User Invitations API - Routes for inviting users to platform or projects

Endpoints:
- GET /api/v1/invitations - List invitations
- POST /api/v1/invitations - Create invitation
- GET /api/v1/invitations/:id - Get invitation
- POST /api/v1/invitations/:id/accept - Accept invitation
- DELETE /api/v1/invitations/:id - Revoke invitation
"""

from flask import Blueprint, request, jsonify
from uuid import UUID, uuid4
from datetime import datetime
import logging

from app.database import db
from app.models.permissions import UserInvitation

logger = logging.getLogger(__name__)

invitations_bp = Blueprint('invitations', __name__, url_prefix='/api/v1/invitations')


@invitations_bp.route('', methods=['GET'])
def list_invitations():
    """
    List invitations.

    Query params:
        platform_id: Filter by platform
        project_id: Filter by project
        email: Filter by email
        status: Filter by status (pending, accepted, expired)
    """
    platform_id = request.args.get('platform_id')
    project_id = request.args.get('project_id')
    email = request.args.get('email')
    status = request.args.get('status')

    query = UserInvitation.query

    if platform_id:
        query = query.filter_by(platform_id=UUID(platform_id))

    if project_id:
        query = query.filter_by(project_id=UUID(project_id))

    if email:
        query = query.filter_by(email=email)

    if status:
        query = query.filter_by(status=status)

    invitations = query.order_by(UserInvitation.created_at.desc()).all()

    return jsonify({
        'invitations': [_serialize_invitation(i) for i in invitations],
        'count': len(invitations)
    }), 200


@invitations_bp.route('', methods=['POST'])
def create_invitation():
    """
    Create an invitation.

    Body for PLATFORM invitation:
        {
            "type": "PLATFORM",
            "platform_id": "uuid",
            "email": "user@example.com",
            "platform_role": "MEMBER"
        }

    Body for PROJECT invitation:
        {
            "type": "PROJECT",
            "platform_id": "uuid",
            "project_id": "uuid",
            "email": "user@example.com",
            "project_role_id": "uuid"
        }
    """
    data = request.get_json()

    # Validate required fields
    required = ['type', 'platform_id', 'email']
    for field in required:
        if field not in data:
            return jsonify({'error': f'{field} is required'}), 400

    invitation_type = data['type']

    if invitation_type not in ['PLATFORM', 'PROJECT']:
        return jsonify({'error': 'type must be PLATFORM or PROJECT'}), 400

    try:
        # Check if invitation already exists
        existing = UserInvitation.query.filter_by(
            email=data['email'],
            platform_id=UUID(data['platform_id']),
            status='PENDING'
        ).first()

        if existing:
            return jsonify({'error': 'Invitation already exists for this email'}), 400

        invitation = UserInvitation(
            id=uuid4(),
            platform_id=UUID(data['platform_id']),
            email=data['email'],
            type=invitation_type,
            status='PENDING',
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        if invitation_type == 'PLATFORM':
            if 'platform_role' not in data:
                return jsonify({'error': 'platform_role is required for PLATFORM invitations'}), 400
            invitation.platform_role = data['platform_role']

        elif invitation_type == 'PROJECT':
            if 'project_id' not in data or 'project_role_id' not in data:
                return jsonify({'error': 'project_id and project_role_id are required for PROJECT invitations'}), 400
            invitation.project_id = UUID(data['project_id'])
            invitation.project_role_id = UUID(data['project_role_id'])

        db.session.add(invitation)
        db.session.commit()

        logger.info(f"Created invitation: {invitation.id} for {data['email']}")

        return jsonify(_serialize_invitation(invitation)), 201

    except Exception as e:
        logger.error(f"Error creating invitation: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@invitations_bp.route('/<invitation_id>', methods=['GET'])
def get_invitation(invitation_id):
    """Get invitation details."""
    try:
        invitation = db.session.get(UserInvitation, UUID(invitation_id))
        if not invitation:
            return jsonify({'error': 'Invitation not found'}), 404

        return jsonify(_serialize_invitation(invitation, include_details=True)), 200

    except Exception as e:
        logger.error(f"Error getting invitation: {e}")
        return jsonify({'error': str(e)}), 500


@invitations_bp.route('/<invitation_id>/accept', methods=['POST'])
def accept_invitation(invitation_id):
    """
    Accept an invitation.

    Body:
        {
            "user_id": "uuid"  # ID of the user accepting
        }
    """
    try:
        invitation = db.session.get(UserInvitation, UUID(invitation_id))
        if not invitation:
            return jsonify({'error': 'Invitation not found'}), 404

        if invitation.status != 'PENDING':
            return jsonify({'error': f'Invitation is {invitation.status}'}), 400

        data = request.get_json()
        user_id = data.get('user_id')

        if not user_id:
            return jsonify({'error': 'user_id is required'}), 400

        # Update invitation
        invitation.status = 'ACCEPTED'
        invitation.updated_at = datetime.utcnow()

        # Add user to platform or project
        if invitation.type == 'PLATFORM':
            # Update user's platform_role
            from app.models.organization import User
            user = db.session.get(User, UUID(user_id))
            if user:
                user.platform_id = invitation.platform_id
                user.platform_role = invitation.platform_role

        elif invitation.type == 'PROJECT':
            # Add user as project member
            from app.models.permissions import ProjectMember
            member = ProjectMember(
                id=uuid4(),
                project_id=invitation.project_id,
                user_id=UUID(user_id),
                project_role_id=invitation.project_role_id,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.session.add(member)

        db.session.commit()

        logger.info(f"Accepted invitation: {invitation_id}")

        return jsonify(_serialize_invitation(invitation)), 200

    except Exception as e:
        logger.error(f"Error accepting invitation: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@invitations_bp.route('/<invitation_id>', methods=['DELETE'])
def revoke_invitation(invitation_id):
    """Revoke (delete) an invitation."""
    try:
        invitation = db.session.get(UserInvitation, UUID(invitation_id))
        if not invitation:
            return jsonify({'error': 'Invitation not found'}), 404

        db.session.delete(invitation)
        db.session.commit()

        logger.info(f"Revoked invitation: {invitation_id}")

        return jsonify({'message': 'Invitation revoked successfully'}), 200

    except Exception as e:
        logger.error(f"Error revoking invitation: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


def _serialize_invitation(invitation: UserInvitation, include_details: bool = False) -> dict:
    """Serialize invitation to dict."""
    data = {
        'id': str(invitation.id),
        'platform_id': str(invitation.platform_id),
        'email': invitation.email,
        'type': invitation.type,
        'status': invitation.status,
        'created_at': invitation.created_at.isoformat() if invitation.created_at else None,
        'updated_at': invitation.updated_at.isoformat() if invitation.updated_at else None,
    }

    if invitation.type == 'PLATFORM':
        data['platform_role'] = invitation.platform_role

    elif invitation.type == 'PROJECT':
        data['project_id'] = str(invitation.project_id) if invitation.project_id else None
        data['project_role_id'] = str(invitation.project_role_id) if invitation.project_role_id else None

    if include_details:
        # Include platform name
        from app.models.platform import Platform
        platform = db.session.get(Platform, invitation.platform_id)
        if platform:
            data['platform_name'] = platform.name

        # Include project name if PROJECT invitation
        if invitation.type == 'PROJECT' and invitation.project_id:
            from app.models.platform import Project
            project = db.session.get(Project, invitation.project_id)
            if project:
                data['project_name'] = project.name

    return data
