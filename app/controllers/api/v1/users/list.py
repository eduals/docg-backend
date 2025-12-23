"""
List Users Controller.
"""

from flask import jsonify, g
from app.models import User


def list_users():
    """Lista usuários da organização"""
    org_id = g.organization_id

    users = User.query.filter_by(organization_id=org_id).all()

    return jsonify({
        'users': [user.to_dict() for user in users]
    })
