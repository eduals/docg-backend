"""
Trigger Processor - Processa trigger steps.

Responsável por:
- Identificar o tipo de trigger (hubspot, webhook, google-forms)
- Buscar dados da fonte
- Normalizar output para uso nos steps seguintes
"""

from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


async def process_trigger_step(
    node: Any,
    trigger_data: Dict[str, Any] = None,
    context: Any = None,
) -> Dict[str, Any]:
    """
    Processa um trigger step.

    Args:
        node: WorkflowNode trigger
        trigger_data: Dados do trigger (webhook payload, object_id, etc)
        context: GlobalVariable context

    Returns:
        Dict com dados extraídos do trigger
    """
    from app.apps import AppRegistry

    node_type = node.node_type
    config = node.config or {}

    # Determinar trigger type real (pode estar em config)
    actual_trigger_type = config.get('trigger_type', node_type)
    if node_type == 'trigger':
        actual_trigger_type = config.get('trigger_type', 'hubspot')

    # Obter app correspondente
    app = AppRegistry.get(actual_trigger_type)

    if app:
        triggers = app.get_triggers()
        if triggers:
            trigger = triggers[0]  # Usar primeiro trigger disponível
            connection_id = config.get('source_connection_id')

            try:
                result = await app.execute_trigger(
                    trigger_key=trigger.key,
                    connection_id=connection_id,
                    trigger_data=trigger_data,
                    context=context,
                )
                return result
            except Exception as e:
                logger.error(f"Error executing trigger {trigger.key}: {e}")
                raise

    # Fallback para processamento legado
    return await _execute_legacy_trigger(node, trigger_data, context)


async def _execute_legacy_trigger(
    node: Any,
    trigger_data: Dict[str, Any],
    context: Any,
) -> Dict[str, Any]:
    """
    Fallback para processar trigger via código legado.

    Suporta:
    - HubSpot: busca dados do objeto
    - Webhook: usa payload recebido
    - Google Forms: busca resposta do formulário
    """
    from app.models import DataSourceConnection

    config = node.config or {}
    trigger_type = config.get('trigger_type', node.node_type)

    if trigger_type in ('hubspot', 'trigger') and config.get('source_connection_id'):
        # HubSpot trigger - buscar dados do objeto
        return await _process_hubspot_trigger(config, trigger_data)

    elif trigger_type == 'webhook':
        # Webhook trigger - usar dados recebidos
        return _process_webhook_trigger(config, trigger_data)

    elif trigger_type == 'google-forms':
        # Google Forms trigger
        return await _process_google_forms_trigger(config, trigger_data)

    else:
        # Retornar dados como estão
        return trigger_data or {}


async def _process_hubspot_trigger(config: Dict[str, Any], trigger_data: Dict[str, Any]) -> Dict[str, Any]:
    """Processa trigger HubSpot."""
    from app.services.data_sources.hubspot import HubSpotDataSource
    from app.models import DataSourceConnection

    connection_id = config.get('source_connection_id')
    object_type = config.get('source_object_type', 'contact')

    # Obter object_id dos dados do trigger
    object_id = trigger_data.get('objectId') or trigger_data.get('object_id') or trigger_data.get('id')

    if not object_id:
        logger.warning("No object_id in trigger_data for HubSpot trigger")
        return trigger_data

    connection = DataSourceConnection.query.get(connection_id)
    if not connection:
        raise ValueError(f"Connection {connection_id} not found")

    data_source = HubSpotDataSource(connection)
    object_data = data_source.get_object_data(object_type, str(object_id))

    return {
        'source': 'hubspot',
        'object_type': object_type,
        'object_id': object_id,
        'data': object_data,
        **object_data.get('properties', {}),
    }


def _process_webhook_trigger(config: Dict[str, Any], trigger_data: Dict[str, Any]) -> Dict[str, Any]:
    """Processa trigger webhook."""
    field_mapping = config.get('field_mapping', {})

    # Aplicar field mapping se configurado
    if field_mapping:
        mapped_data = {}
        for target_field, source_path in field_mapping.items():
            value = _get_nested_value(trigger_data, source_path.split('.'))
            if value is not None:
                mapped_data[target_field] = value
        return {
            'source': 'webhook',
            'raw': trigger_data,
            **mapped_data,
        }

    return {
        'source': 'webhook',
        **trigger_data,
    }


async def _process_google_forms_trigger(config: Dict[str, Any], trigger_data: Dict[str, Any]) -> Dict[str, Any]:
    """Processa trigger Google Forms."""
    form_id = config.get('form_id')
    response_id = trigger_data.get('response_id')

    if form_id and response_id:
        from app.services.data_sources.google_forms import GoogleFormsDataSource
        from app.models import DataSourceConnection

        connection_id = config.get('source_connection_id')
        if connection_id:
            connection = DataSourceConnection.query.get(connection_id)
            if connection:
                data_source = GoogleFormsDataSource(connection)
                responses = data_source.get_form_responses(form_id)
                # Encontrar a resposta específica
                for response in responses:
                    if response.get('responseId') == response_id:
                        return {
                            'source': 'google-forms',
                            'form_id': form_id,
                            'response_id': response_id,
                            **response,
                        }

    return {
        'source': 'google-forms',
        **trigger_data,
    }


def _get_nested_value(obj: Any, keys: list) -> Any:
    """Obtém valor aninhado."""
    for key in keys:
        if isinstance(obj, dict):
            obj = obj.get(key)
        else:
            return None
        if obj is None:
            return None
    return obj
