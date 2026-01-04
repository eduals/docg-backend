"""
Connection Keys API - Routes for managing global OAuth app credentials

Endpoints:
- GET /api/v1/connection-keys - List connection keys
- POST /api/v1/connection-keys - Create connection key
- GET /api/v1/connection-keys/:id - Get connection key
- PUT /api/v1/connection-keys/:id - Update connection key
- DELETE /api/v1/connection-keys/:id - Delete connection key
"""

from flask import Blueprint, request, jsonify
from uuid import UUID, uuid4
from datetime import datetime
import logging

from app.database import db
from app.models.app_connection import ConnectionKey
from app.utils.credentials_encryption import encrypt_credentials, decrypt_credentials

logger = logging.getLogger(__name__)

connection_keys_bp = Blueprint('connection_keys', __name__, url_prefix='/api/v1/connection-keys')


@connection_keys_bp.route('', methods=['GET'])
def list_connection_keys():
    """
    List all connection keys.

    Query params:
        piece_name: Filter by piece
    """
    piece_name = request.args.get('piece_name')

    query = ConnectionKey.query

    if piece_name:
        query = query.filter_by(piece_name=piece_name)

    keys = query.order_by(ConnectionKey.piece_name).all()

    return jsonify({
        'connection_keys': [_serialize_key(k) for k in keys],
        'count': len(keys)
    }), 200


@connection_keys_bp.route('', methods=['POST'])
def create_connection_key():
    """
    Create a new connection key.

    Body:
        {
            "piece_name": "hubspot",
            "client_id": "...",
            "client_secret": "..."
        }
    """
    data = request.get_json()

    # Validate required fields
    required = ['piece_name', 'client_id', 'client_secret']
    for field in required:
        if field not in data:
            return jsonify({'error': f'{field} is required'}), 400

    try:
        # Check if key already exists for this piece
        existing = ConnectionKey.query.filter_by(piece_name=data['piece_name']).first()
        if existing:
            return jsonify({'error': 'Connection key already exists for this piece'}), 400

        # Encrypt client_secret
        encrypted_secret = encrypt_credentials({'client_secret': data['client_secret']})

        key = ConnectionKey(
            id=uuid4(),
            piece_name=data['piece_name'],
            client_id=data['client_id'],
            client_secret=encrypted_secret,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        db.session.add(key)
        db.session.commit()

        logger.info(f"Created connection key for piece: {data['piece_name']}")

        return jsonify(_serialize_key(key)), 201

    except Exception as e:
        logger.error(f"Error creating connection key: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@connection_keys_bp.route('/<key_id>', methods=['GET'])
def get_connection_key(key_id):
    """Get connection key details (without decrypted secret)."""
    try:
        key = db.session.get(ConnectionKey, UUID(key_id))
        if not key:
            return jsonify({'error': 'Connection key not found'}), 404

        return jsonify(_serialize_key(key)), 200

    except Exception as e:
        logger.error(f"Error getting connection key: {e}")
        return jsonify({'error': str(e)}), 500


@connection_keys_bp.route('/<key_id>', methods=['PUT'])
def update_connection_key(key_id):
    """
    Update connection key.

    Body:
        {
            "client_id": "...",
            "client_secret": "..."  # Will be encrypted
        }
    """
    try:
        key = db.session.get(ConnectionKey, UUID(key_id))
        if not key:
            return jsonify({'error': 'Connection key not found'}), 404

        data = request.get_json()

        # Update fields
        if 'client_id' in data:
            key.client_id = data['client_id']

        if 'client_secret' in data:
            # Encrypt new secret
            encrypted_secret = encrypt_credentials({'client_secret': data['client_secret']})
            key.client_secret = encrypted_secret

        key.updated_at = datetime.utcnow()

        db.session.commit()

        logger.info(f"Updated connection key: {key_id}")

        return jsonify(_serialize_key(key)), 200

    except Exception as e:
        logger.error(f"Error updating connection key: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@connection_keys_bp.route('/<key_id>', methods=['DELETE'])
def delete_connection_key(key_id):
    """Delete a connection key."""
    try:
        key = db.session.get(ConnectionKey, UUID(key_id))
        if not key:
            return jsonify({'error': 'Connection key not found'}), 404

        db.session.delete(key)
        db.session.commit()

        logger.info(f"Deleted connection key: {key_id}")

        return jsonify({'message': 'Connection key deleted successfully'}), 200

    except Exception as e:
        logger.error(f"Error deleting connection key: {e}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


def _serialize_key(key: ConnectionKey) -> dict:
    """Serialize connection key to dict (WITHOUT decrypted secret)."""
    return {
        'id': str(key.id),
        'piece_name': key.piece_name,
        'client_id': key.client_id,
        # NOTE: Never return decrypted secret in API
        'has_client_secret': bool(key.client_secret),
        'created_at': key.created_at.isoformat() if key.created_at else None,
        'updated_at': key.updated_at.isoformat() if key.updated_at else None,
    }
