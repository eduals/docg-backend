"""
Platforms API - Routes for managing platforms (tenants)

Endpoints:
- GET /api/v1/platforms - List platforms
- POST /api/v1/platforms - Create platform
- GET /api/v1/platforms/:id - Get platform details
- PUT /api/v1/platforms/:id - Update platform
- DELETE /api/v1/platforms/:id - Delete platform
"""

from flask import Blueprint, request, jsonify
from uuid import UUID, uuid4
from datetime import datetime
import logging

from app.database import db
from app.models.platform import Platform

logger = logging.getLogger(__name__)

platforms_bp = Blueprint('platforms', __name__, url_prefix='/api/v1/platforms')


@platforms_bp.route('', methods=['GET'])
def list_platforms():
    """List all platforms."""
    try:
        platforms = Platform.query.order_by(Platform.created_at.desc()).all()

        return jsonify({
            'platforms': [_serialize_platform(p) for p in platforms],
            'count': len(platforms)
        }), 200

    except Exception as e:
        logger.error(f"Error listing platforms: {e}")
        return jsonify({'error': str(e)}), 500


@platforms_bp.route('', methods=['POST'])
def create_platform():
    """
    Create a new platform.

    Body:
        {
            "name": "My Platform",
            "sso_enabled": false,
            "filter_pieces_enabled": false,
            "allowed_pieces": ["hubspot", "webhook"],
            "max_projects": 10,
            "primary_color": "#4A90E2",
            "logo_url": "https://...",
            "full_logo_url": "https://..."
        }
    """
    data = request.get_json()

    # Validate required fields
    if not data.get('name'):
        return jsonify({'error': 'name is required'}), 400

    try:
        platform = Platform(
            id=uuid4(),
            name=data['name'],
            sso_enabled=data.get('sso_enabled', False),
            filter_pieces_enabled=data.get('filter_pieces_enabled', False),
            allowed_pieces=data.get('allowed_pieces'),
            max_projects=data.get('max_projects'),
            primary_color=data.get('primary_color'),
            logo_url=data.get('logo_url'),
            full_logo_url=data.get('full_logo_url'),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        db.session.add(platform)
        db.session.commit()

        logger.info(f"Created platform: {platform.id} - {platform.name}")

        return jsonify(_serialize_platform(platform)), 201

    except Exception as e:
        logger.error(f"Error creating platform: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@platforms_bp.route('/<platform_id>', methods=['GET'])
def get_platform(platform_id):
    """Get platform details."""
    try:
        platform = db.session.get(Platform, UUID(platform_id))
        if not platform:
            return jsonify({'error': 'Platform not found'}), 404

        return jsonify(_serialize_platform(platform, include_stats=True)), 200

    except Exception as e:
        logger.error(f"Error getting platform: {e}")
        return jsonify({'error': str(e)}), 500


@platforms_bp.route('/<platform_id>', methods=['PUT'])
def update_platform(platform_id):
    """
    Update platform.

    Body:
        {
            "name": "Updated name",
            "sso_enabled": true,
            ...
        }
    """
    try:
        platform = db.session.get(Platform, UUID(platform_id))
        if not platform:
            return jsonify({'error': 'Platform not found'}), 404

        data = request.get_json()

        # Update fields
        updateable_fields = [
            'name', 'sso_enabled', 'filter_pieces_enabled', 'allowed_pieces',
            'max_projects', 'primary_color', 'logo_url', 'full_logo_url'
        ]

        for field in updateable_fields:
            if field in data:
                setattr(platform, field, data[field])

        platform.updated_at = datetime.utcnow()

        db.session.commit()

        logger.info(f"Updated platform: {platform.id}")

        return jsonify(_serialize_platform(platform)), 200

    except Exception as e:
        logger.error(f"Error updating platform: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@platforms_bp.route('/<platform_id>', methods=['DELETE'])
def delete_platform(platform_id):
    """Delete a platform (cascade deletes projects, flows, etc)."""
    try:
        platform = db.session.get(Platform, UUID(platform_id))
        if not platform:
            return jsonify({'error': 'Platform not found'}), 404

        db.session.delete(platform)
        db.session.commit()

        logger.info(f"Deleted platform: {platform_id}")

        return jsonify({'message': 'Platform deleted successfully'}), 200

    except Exception as e:
        logger.error(f"Error deleting platform: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


def _serialize_platform(platform: Platform, include_stats: bool = False) -> dict:
    """Serialize platform to dict."""
    data = {
        'id': str(platform.id),
        'name': platform.name,
        'sso_enabled': platform.sso_enabled,
        'filter_pieces_enabled': platform.filter_pieces_enabled,
        'allowed_pieces': platform.allowed_pieces,
        'max_projects': platform.max_projects,
        'primary_color': platform.primary_color,
        'logo_url': platform.logo_url,
        'full_logo_url': platform.full_logo_url,
        'created_at': platform.created_at.isoformat() if platform.created_at else None,
        'updated_at': platform.updated_at.isoformat() if platform.updated_at else None,
    }

    if include_stats:
        # Add project count and user count
        from app.models.platform import Project
        from app.models.organization import User

        project_count = Project.query.filter_by(platform_id=platform.id).count()
        user_count = User.query.filter_by(platform_id=platform.id).count()

        data['project_count'] = project_count
        data['user_count'] = user_count

    return data
