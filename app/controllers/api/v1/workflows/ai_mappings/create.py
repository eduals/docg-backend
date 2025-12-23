"""
Create AI Mapping Controller.
"""

import logging
from flask import request, jsonify, g
from app.database import db
from app.models import Workflow, AIGenerationMapping, DataSourceConnection

logger = logging.getLogger(__name__)

AI_PROVIDERS = ['openai', 'gemini', 'anthropic']


def create_ai_mapping(workflow_id: str):
    """
    Cria um novo mapeamento de IA para o workflow.

    Body:
    {
        "ai_tag": "paragrapho1",
        "source_fields": ["dealname", "amount", "company.name"],
        "provider": "openai",
        "model": "gpt-4",
        "ai_connection_id": "uuid",
        "prompt_template": "Gere um parágrafo descrevendo o deal {{dealname}}...",
        "temperature": 0.7,
        "max_tokens": 500,
        "fallback_value": "[Texto não gerado]"
    }
    """
    workflow = Workflow.query.filter_by(
        id=workflow_id,
        organization_id=g.organization_id
    ).first_or_404()

    data = request.get_json()

    # Validações
    required = ['ai_tag', 'provider', 'model']
    for field in required:
        if not data.get(field):
            return jsonify({'error': f'{field} é obrigatório'}), 400

    # Validar provider
    provider = data['provider'].lower()
    if provider not in AI_PROVIDERS:
        return jsonify({
            'error': f'Provedor não suportado. Use: {", ".join(AI_PROVIDERS)}'
        }), 400

    # Validar ai_connection_id se fornecido
    ai_connection_id = data.get('ai_connection_id')
    if ai_connection_id:
        connection = DataSourceConnection.query.filter_by(
            id=ai_connection_id,
            organization_id=g.organization_id,
            source_type=provider
        ).first()
        if not connection:
            return jsonify({
                'error': 'Conexão de IA não encontrada ou não corresponde ao provider'
            }), 400

    # Verificar se tag já existe no workflow
    existing = AIGenerationMapping.query.filter_by(
        workflow_id=workflow.id,
        ai_tag=data['ai_tag']
    ).first()

    if existing:
        return jsonify({
            'error': f'Tag AI "{data["ai_tag"]}" já existe neste workflow'
        }), 409

    # Criar mapeamento
    mapping = AIGenerationMapping(
        workflow_id=workflow.id,
        ai_tag=data['ai_tag'],
        source_fields=data.get('source_fields', []),
        provider=provider,
        model=data['model'],
        ai_connection_id=ai_connection_id,
        prompt_template=data.get('prompt_template'),
        temperature=data.get('temperature', 0.7),
        max_tokens=data.get('max_tokens', 1000),
        fallback_value=data.get('fallback_value')
    )

    db.session.add(mapping)
    db.session.commit()

    logger.info(f"AI mapping criado: workflow={workflow_id}, tag={data['ai_tag']}")

    return jsonify({
        'success': True,
        'ai_mapping': mapping.to_dict()
    }), 201
