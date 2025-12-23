"""
Create Workflow Node Controller.
"""

import logging
from flask import request, jsonify, g
from sqlalchemy.exc import IntegrityError
from app.database import db
from app.models import Workflow, WorkflowNode
from app.models.workflow import TRIGGER_NODE_TYPES

logger = logging.getLogger(__name__)


def create_workflow_node(workflow_id: str):
    """
    Cria um novo node no workflow.

    Body:
    {
        "node_type": "google-docs",
        "position": 2,
        "parent_node_id": "uuid",
        "config": {}
    }
    """
    try:
        workflow = Workflow.query.filter_by(
            id=workflow_id,
            organization_id=g.organization_id
        ).first_or_404()

        data = request.get_json()
        if not data:
            return jsonify({'error': 'Request body é obrigatório'}), 400

        # Validações
        if not data.get('node_type'):
            return jsonify({'error': 'node_type é obrigatório'}), 400

        node_type = data['node_type']
        valid_types = [
            # Triggers
            'hubspot', 'webhook', 'google-forms',
            # Documentos
            'google-docs', 'google-slides', 'microsoft-word', 'microsoft-powerpoint', 'file-upload',
            # Email
            'gmail', 'outlook',
            # Human in the Loop
            'review-documents', 'request-signatures',
            # Compatibilidade (DEPRECATED)
            'trigger', 'human-in-loop', 'clicksign', 'signature',
        ]

        if node_type not in valid_types:
            return jsonify({
                'error': f'node_type deve ser um de: {", ".join(valid_types)}'
            }), 400

        # Se for qualquer tipo de trigger, verificar se já existe
        if node_type in TRIGGER_NODE_TYPES:
            existing_trigger = WorkflowNode.query.filter(
                WorkflowNode.workflow_id == workflow.id,
                WorkflowNode.node_type.in_(TRIGGER_NODE_TYPES)
            ).first()
            if existing_trigger:
                return jsonify({
                    'error': 'Workflow já possui um trigger node. Cada workflow pode ter apenas um trigger.'
                }), 400

        # Determinar position se não fornecido
        position = data.get('position')
        if not position:
            last_node = WorkflowNode.query.filter_by(
                workflow_id=workflow.id
            ).order_by(WorkflowNode.position.desc()).first()
            position = (last_node.position + 1) if last_node else 1

        # Se position for 1 e não for trigger, retornar erro
        if position == 1 and node_type not in ['hubspot', 'webhook', 'google-forms']:
            return jsonify({
                'error': 'O primeiro node (position=1) deve ser um trigger (hubspot, webhook ou google-forms)'
            }), 400

        # Validar parent_node_id se fornecido
        parent_node_id = data.get('parent_node_id')
        if parent_node_id:
            parent = WorkflowNode.query.filter_by(
                id=parent_node_id,
                workflow_id=workflow.id
            ).first()
            if not parent:
                return jsonify({'error': 'parent_node_id não encontrado'}), 400

        # Validar e limpar config
        config = data.get('config', {})
        if not isinstance(config, dict):
            config = {}

        # Remover valores None para evitar problemas com JSONB
        cleaned_config = {k: v for k, v in config.items() if v is not None}

        # Criar node
        node = WorkflowNode(
            workflow_id=workflow.id,
            node_type=node_type,
            position=position,
            parent_node_id=parent_node_id,
            config=cleaned_config,
            status='draft'
        )

        db.session.add(node)
        db.session.commit()

        return jsonify({
            'success': True,
            'node': node.to_dict(include_config=True)
        }), 201

    except IntegrityError as e:
        db.session.rollback()
        error_msg = str(e.orig) if hasattr(e, 'orig') else str(e)
        if 'unique_workflow_position' in error_msg.lower():
            position_used = data.get('position', 'desconhecida') if 'data' in dir() else 'desconhecida'
            return jsonify({
                'error': f'Já existe um node na posição {position_used}. Por favor, escolha outra posição.'
            }), 400
        logger.error(f'IntegrityError ao criar node: {error_msg}')
        return jsonify({'error': 'Erro ao criar node: violação de constraint única'}), 400

    except Exception as e:
        db.session.rollback()
        logger.error(f'Erro ao criar node no workflow {workflow_id}: {str(e)}', exc_info=True)
        return jsonify({
            'error': f'Erro ao criar node: {str(e)}'
        }), 500
