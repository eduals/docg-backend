"""
Helpers para Workflows Controllers.
"""

from typing import Dict, Any, Tuple, Optional
from app.models import Workflow


def validate_post_actions(post_actions: Optional[Dict[str, Any]]) -> Tuple[bool, Optional[str]]:
    """
    Valida a estrutura de post_actions.

    Args:
        post_actions: Dict com configurações de post_actions

    Returns:
        Tuple (is_valid, error_message)
    """
    if not post_actions or not isinstance(post_actions, dict):
        return True, None  # post_actions é opcional

    hubspot_config = post_actions.get('hubspot_attachment')
    if not hubspot_config:
        return True, None  # Não há configuração HubSpot, tudo OK

    if not isinstance(hubspot_config, dict):
        return False, 'hubspot_attachment deve ser um objeto'

    # Validar enabled
    if 'enabled' in hubspot_config and not isinstance(hubspot_config['enabled'], bool):
        return False, 'hubspot_attachment.enabled deve ser um booleano'

    # Se enabled, validar attachment_type
    if hubspot_config.get('enabled'):
        attachment_type = hubspot_config.get('attachment_type', 'engagement')
        if attachment_type not in ['engagement', 'property']:
            return False, 'hubspot_attachment.attachment_type deve ser "engagement" ou "property"'

        # Se attachment_type é 'property', property_name é obrigatório
        if attachment_type == 'property':
            if not hubspot_config.get('property_name'):
                return False, 'hubspot_attachment.property_name é obrigatório quando attachment_type é "property"'

    return True, None


def workflow_to_dict(
    workflow: Workflow,
    include_mappings: bool = False,
    include_ai_mappings: bool = False
) -> dict:
    """Converte workflow para dicionário"""
    result = {
        'id': str(workflow.id),
        'name': workflow.name,
        'description': workflow.description,
        'status': workflow.status,
        'post_actions': workflow.post_actions,
        'created_at': workflow.created_at.isoformat() if workflow.created_at else None,
        'updated_at': workflow.updated_at.isoformat() if workflow.updated_at else None
    }

    # Manter campos legados para compatibilidade durante transição (deprecated)
    result['source_connection_id'] = str(workflow.source_connection_id) if workflow.source_connection_id else None
    result['source_object_type'] = workflow.source_object_type
    result['template_id'] = str(workflow.template_id) if workflow.template_id else None
    result['output_folder_id'] = workflow.output_folder_id
    result['output_name_template'] = workflow.output_name_template
    result['create_pdf'] = workflow.create_pdf
    result['trigger_type'] = workflow.trigger_type
    result['trigger_config'] = workflow.trigger_config

    if include_mappings:
        result['field_mappings'] = [
            {
                'id': str(m.id),
                'template_tag': m.template_tag,
                'source_field': m.source_field,
                'transform_type': m.transform_type,
                'transform_config': m.transform_config,
                'default_value': m.default_value
            }
            for m in workflow.field_mappings
        ]

    if include_ai_mappings:
        result['ai_mappings'] = [m.to_dict() for m in workflow.ai_mappings]

    # Incluir info do template se disponível (legado)
    if workflow.template:
        result['template'] = {
            'id': str(workflow.template.id),
            'name': workflow.template.name,
            'google_file_type': workflow.template.google_file_type,
            'thumbnail_url': workflow.template.thumbnail_url
        }

    return result
