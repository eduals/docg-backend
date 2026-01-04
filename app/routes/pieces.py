"""
Pieces API - Routes for piece metadata

Endpoints:
- GET /api/v1/pieces - List all available pieces
- GET /api/v1/pieces/:name - Get piece details
"""

from flask import Blueprint, request, jsonify
import logging

from app.pieces.base import registry

logger = logging.getLogger(__name__)

pieces_bp = Blueprint('pieces', __name__, url_prefix='/api/v1/pieces')


@pieces_bp.route('', methods=['GET'])
def list_pieces():
    """
    List all available pieces.

    Query params:
        category: Filter by category (optional)
    """
    try:
        all_pieces = registry.get_all()

        pieces_data = []
        for piece_name, piece in all_pieces.items():
            pieces_data.append(_serialize_piece_summary(piece))

        return jsonify({
            'pieces': pieces_data,
            'count': len(pieces_data)
        }), 200

    except Exception as e:
        logger.error(f"Error listing pieces: {e}")
        return jsonify({'error': str(e)}), 500


@pieces_bp.route('/<piece_name>', methods=['GET'])
def get_piece(piece_name):
    """Get detailed information about a piece."""
    try:
        piece = registry.get(piece_name)
        if not piece:
            return jsonify({'error': 'Piece not found'}), 404

        return jsonify(_serialize_piece_detail(piece)), 200

    except Exception as e:
        logger.error(f"Error getting piece: {e}")
        return jsonify({'error': str(e)}), 500


def _serialize_piece_summary(piece) -> dict:
    """Serialize piece summary (for list view)."""
    return {
        'name': piece.name,
        'display_name': piece.display_name,
        'description': piece.description if hasattr(piece, 'description') else None,
        'logo_url': piece.logo_url if hasattr(piece, 'logo_url') else None,
        'requires_auth': piece.auth is not None,
        'auth_type': piece.auth.type.value if piece.auth else None,
        'action_count': len(piece.actions),
        'trigger_count': len(piece.triggers),
    }


def _serialize_piece_detail(piece) -> dict:
    """Serialize piece with full details."""
    data = {
        'name': piece.name,
        'display_name': piece.display_name,
        'description': piece.description if hasattr(piece, 'description') else None,
        'logo_url': piece.logo_url if hasattr(piece, 'logo_url') else None,
        'version': piece.version if hasattr(piece, 'version') else None,
        'auth': _serialize_auth(piece.auth) if piece.auth else None,
        'actions': [_serialize_action(action) for action in piece.actions],
        'triggers': [_serialize_trigger(trigger) for trigger in piece.triggers],
    }

    return data


def _serialize_auth(auth) -> dict:
    """Serialize auth configuration."""
    data = {
        'type': auth.type.value,
        'required': auth.required,
    }

    if hasattr(auth, 'oauth2_config') and auth.oauth2_config:
        data['oauth2'] = {
            'auth_url': auth.oauth2_config.auth_url,
            'token_url': auth.oauth2_config.token_url,
            'scope': auth.oauth2_config.scope,
        }

    return data


def _serialize_action(action) -> dict:
    """Serialize action."""
    return {
        'name': action.name,
        'display_name': action.display_name,
        'description': action.description if hasattr(action, 'description') else None,
        'properties': [_serialize_property(prop) for prop in action.properties],
    }


def _serialize_trigger(trigger) -> dict:
    """Serialize trigger."""
    return {
        'name': trigger.name,
        'display_name': trigger.display_name if hasattr(trigger, 'display_name') else trigger.name,
        'description': trigger.description if hasattr(trigger, 'description') else None,
        'type': trigger.type if hasattr(trigger, 'type') else 'WEBHOOK',
        'properties': [_serialize_property(prop) for prop in trigger.properties] if hasattr(trigger, 'properties') else [],
    }


def _serialize_property(prop) -> dict:
    """Serialize property."""
    data = {
        'name': prop.name,
        'display_name': prop.display_name,
        'description': prop.description if hasattr(prop, 'description') else None,
        'type': prop.type.value,
        'required': prop.required,
    }

    if prop.options:
        data['options'] = prop.options

    if hasattr(prop, 'default_value') and prop.default_value is not None:
        data['default_value'] = prop.default_value

    return data
