"""
Update AI Mapping Controller.
"""

from flask import request, jsonify, g
from app.database import db
from app.models import Workflow, AIGenerationMapping, DataSourceConnection

AI_PROVIDERS = ['openai', 'gemini', 'anthropic']


def update_ai_mapping(workflow_id: str, mapping_id: str):
    """
    Atualiza um mapeamento de IA.

    Body (todos opcionais):
    {
        "source_fields": [...],
        "provider": "gemini",
        "model": "gemini-1.5-pro",
        "ai_connection_id": "uuid",
        "prompt_template": "...",
        "temperature": 0.5,
        "max_tokens": 800,
        "fallback_value": "..."
    }
    """
    workflow = Workflow.query.filter_by(
        id=workflow_id,
        organization_id=g.organization_id
    ).first_or_404()

    mapping = AIGenerationMapping.query.filter_by(
        id=mapping_id,
        workflow_id=workflow.id
    ).first_or_404()

    data = request.get_json()

    # Atualizar campos permitidos
    if 'source_fields' in data:
        mapping.source_fields = data['source_fields']

    if 'provider' in data:
        provider = data['provider'].lower()
        if provider not in AI_PROVIDERS:
            return jsonify({
                'error': f'Provedor não suportado. Use: {", ".join(AI_PROVIDERS)}'
            }), 400
        mapping.provider = provider

    if 'model' in data:
        mapping.model = data['model']

    if 'ai_connection_id' in data:
        ai_connection_id = data['ai_connection_id']
        if ai_connection_id:
            connection = DataSourceConnection.query.filter_by(
                id=ai_connection_id,
                organization_id=g.organization_id
            ).first()
            if not connection:
                return jsonify({'error': 'Conexão de IA não encontrada'}), 400
        mapping.ai_connection_id = ai_connection_id

    if 'prompt_template' in data:
        mapping.prompt_template = data['prompt_template']

    if 'temperature' in data:
        mapping.temperature = data['temperature']

    if 'max_tokens' in data:
        mapping.max_tokens = data['max_tokens']

    if 'fallback_value' in data:
        mapping.fallback_value = data['fallback_value']

    db.session.commit()

    return jsonify({
        'success': True,
        'ai_mapping': mapping.to_dict()
    })
