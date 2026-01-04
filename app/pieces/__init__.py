"""
Pieces Package - Auto-registers all available pieces

This module automatically imports and registers all pieces when imported.
"""

from app.pieces.base import registry

# Import pieces to trigger registration
from app.pieces.webhook import webhook_piece
from app.pieces.hubspot import hubspot_piece

# List of all registered pieces
__all__ = [
    'registry',
    'webhook_piece',
    'hubspot_piece',
]


def get_all_pieces():
    """
    Get all registered pieces.

    Returns:
        Dict mapping piece names to Piece instances
    """
    return registry.get_all()


def get_piece(piece_name: str):
    """
    Get a specific piece by name.

    Args:
        piece_name: Name of the piece (e.g., "hubspot", "webhook")

    Returns:
        Piece instance or None if not found
    """
    return registry.get(piece_name)


def init_pieces():
    """
    Initialize all pieces.

    This function is called during app startup to ensure all pieces are registered.
    """
    pieces = registry.get_all()
    print(f"[PIECES] Initialized {len(pieces)} pieces:")
    for name in sorted(pieces.keys()):
        piece = pieces[name]
        print(f"  - {name}: {piece.display_name} ({len(piece.actions)} actions, {len(piece.triggers)} triggers)")

    return pieces
