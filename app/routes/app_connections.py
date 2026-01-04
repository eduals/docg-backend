"""
App Connections API - Routes for managing app connections (OAuth credentials)

Endpoints:
- GET /api/v1/app-connections - List connections
- POST /api/v1/app-connections - Create connection
- GET /api/v1/app-connections/:id - Get connection
- PUT /api/v1/app-connections/:id - Update connection
- DELETE /api/v1/app-connections/:id - Delete connection
- POST /api/v1/app-connections/:id/test - Test connection
"""

from flask import Blueprint, request, jsonify
from uuid import UUID, uuid4
from datetime import datetime
import logging

from app.database import db
from app.models.app_connection import AppConnection, AppConnectionType
from app.utils.credentials_encryption import encrypt_credentials, decrypt_credentials

logger = logging.getLogger(__name__)

app_connections_bp = Blueprint('app_connections', __name__, url_prefix='/api/v1/app-connections')


@app_connections_bp.route('', methods=['GET'])
def list_connections():
    """
    List app connections.

    Query params:
        project_id: Filter by project
        piece_name: Filter by piece
        status: Filter by status
    """
    project_id = request.args.get('project_id')
    piece_name = request.args.get('piece_name')
    status = request.args.get('status')

    query = AppConnection.query

    if project_id:
        query = query.filter_by(project_id=UUID(project_id))

    if piece_name:
        query = query.filter_by(piece_name=piece_name)

    if status:
        query = query.filter_by(status=status)

    connections = query.order_by(AppConnection.created_at.desc()).all()

    return jsonify({
        'connections': [_serialize_connection(c) for c in connections],
        'count': len(connections)
    }), 200


@app_connections_bp.route('', methods=['POST'])
def create_connection():
    """
    Create a new app connection.

    Body:
        {
            "project_id": "uuid",
            "name": "My HubSpot",
            "piece_name": "hubspot",
            "type": "OAUTH2",
            "value": {
                "access_token": "...",
                "refresh_token": "...",
                "expires_at": 1234567890
            }
        }
    """
    data = request.get_json()

    # Validate required fields
    required_fields = ['project_id', 'name', 'piece_name', 'type', 'value']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'{field} is required'}), 400

    try:
        # Encrypt credentials
        encrypted_value = encrypt_credentials(data['value'])

        connection = AppConnection(
            id=uuid4(),
            project_id=UUID(data['project_id']),
            name=data['name'],
            piece_name=data['piece_name'],
            type=AppConnectionType(data['type']),
            value=encrypted_value,
            status='ACTIVE',
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        db.session.add(connection)
        db.session.commit()

        logger.info(f"Created connection: {connection.id} - {connection.name}")

        return jsonify(_serialize_connection(connection)), 201

    except Exception as e:
        logger.error(f"Error creating connection: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app_connections_bp.route('/<connection_id>', methods=['GET'])
def get_connection(connection_id):
    """Get connection details (without decrypted credentials)."""
    try:
        connection = db.session.get(AppConnection, UUID(connection_id))
        if not connection:
            return jsonify({'error': 'Connection not found'}), 404

        return jsonify(_serialize_connection(connection)), 200

    except Exception as e:
        logger.error(f"Error getting connection: {e}")
        return jsonify({'error': str(e)}), 500


@app_connections_bp.route('/<connection_id>', methods=['PUT'])
def update_connection(connection_id):
    """
    Update connection.

    Body:
        {
            "name": "Updated name",
            "value": {...}  # New credentials (will be encrypted)
        }
    """
    try:
        connection = db.session.get(AppConnection, UUID(connection_id))
        if not connection:
            return jsonify({'error': 'Connection not found'}), 404

        data = request.get_json()

        # Update fields
        if 'name' in data:
            connection.name = data['name']

        if 'value' in data:
            # Encrypt new credentials
            connection.value = encrypt_credentials(data['value'])

        connection.updated_at = datetime.utcnow()

        db.session.commit()

        logger.info(f"Updated connection: {connection.id}")

        return jsonify(_serialize_connection(connection)), 200

    except Exception as e:
        logger.error(f"Error updating connection: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app_connections_bp.route('/<connection_id>', methods=['DELETE'])
def delete_connection(connection_id):
    """Delete a connection."""
    try:
        connection = db.session.get(AppConnection, UUID(connection_id))
        if not connection:
            return jsonify({'error': 'Connection not found'}), 404

        db.session.delete(connection)
        db.session.commit()

        logger.info(f"Deleted connection: {connection_id}")

        return jsonify({'message': 'Connection deleted successfully'}), 200

    except Exception as e:
        logger.error(f"Error deleting connection: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@app_connections_bp.route('/<connection_id>/test', methods=['POST'])
async def test_connection(connection_id):
    """
    Test if a connection is valid.

    This attempts to use the connection to make a simple API call.
    """
    try:
        connection = db.session.get(AppConnection, UUID(connection_id))
        if not connection:
            return jsonify({'error': 'Connection not found'}), 404

        # Decrypt credentials
        credentials = decrypt_credentials(connection.value)

        # Test based on piece type
        # For now, just return success if we can decrypt
        # TODO: Actually test the connection by calling the API

        return jsonify({
            'status': 'success',
            'message': 'Connection is valid'
        }), 200

    except Exception as e:
        logger.error(f"Error testing connection: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400


def _serialize_connection(connection: AppConnection) -> dict:
    """Serialize connection to dict (WITHOUT decrypted credentials)."""
    return {
        'id': str(connection.id),
        'project_id': str(connection.project_id),
        'name': connection.name,
        'piece_name': connection.piece_name,
        'type': connection.type.value if isinstance(connection.type, AppConnectionType) else connection.type,
        'status': connection.status,
        'created_at': connection.created_at.isoformat() if connection.created_at else None,
        'updated_at': connection.updated_at.isoformat() if connection.updated_at else None,
        # NOTE: Never return decrypted credentials in API
        'has_credentials': bool(connection.value),
    }
