"""
Create Organization Controller.
"""

from flask import request, jsonify
from app.database import db
from app.models import Organization
import re


def create_organization():
    """
    Cria uma nova organização (conta).

    Body:
    {
        "name": "Minha Empresa",
        "billing_email": "billing@empresa.com"
    }
    """
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Body é obrigatório'}), 400

    required = ['name']
    for field in required:
        if not data.get(field):
            return jsonify({'error': f'{field} é obrigatório'}), 400

    # Gerar slug único baseado no nome
    slug_base = re.sub(r'[^a-z0-9]+', '-', data['name'].lower()).strip('-')
    slug = slug_base
    counter = 1

    while Organization.query.filter_by(slug=slug).first():
        slug = f"{slug_base}-{counter}"
        counter += 1

    # Criar organização
    plan_name = data.get('plan', 'free')
    org = Organization(
        name=data['name'],
        slug=slug,
        plan=plan_name,
        billing_email=data.get('billing_email')
    )

    # Aplicar limites do plano
    from app.services.stripe_service import PLAN_CONFIG
    plan_config = PLAN_CONFIG.get(plan_name, {})
    if plan_config:
        org.users_limit = plan_config.get('users_limit', org.users_limit)
        org.documents_limit = plan_config.get('documents_limit', org.documents_limit)
        org.workflows_limit = plan_config.get('workflows_limit', org.workflows_limit)

    db.session.add(org)
    db.session.commit()

    return jsonify({
        'success': True,
        'organization': org.to_dict()
    }), 201
