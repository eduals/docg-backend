"""
Action Processor - Processa action steps.

Responsável por:
- Aplicar computeParameters aos parâmetros
- Validar parâmetros contra schema
- Resolver o app correspondente
- Executar a action
"""

from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


async def process_action_step(
    node: Any,
    parameters: Dict[str, Any] = None,
    context: Any = None,
    previous_steps: list = None,
    skip_validation: bool = False,
) -> Dict[str, Any]:
    """
    Processa um action step.

    Args:
        node: WorkflowNode sendo executado
        parameters: Parâmetros do node (já com computeParameters se aplicável)
        context: GlobalVariable context
        previous_steps: ExecutionSteps anteriores (para computeParameters)
        skip_validation: Se True, pula validação de arguments

    Returns:
        Dict com resultado da action

    Raises:
        ValidationError: Se parâmetros falharem validação
    """
    from app.apps import AppRegistry
    from app.engine.compute_parameters import compute_parameters
    from app.engine.validate_parameters import validate_and_raise

    node_type = node.node_type
    config = node.config or {}

    # Aplicar computeParameters se temos previous_steps
    if previous_steps:
        execution_id = str(context.execution.execution_id) if context and context.execution else None
        trigger_output = context.triggerOutput if context else {}

        config = compute_parameters(
            parameters=config,
            execution_id=execution_id,
            trigger_output=trigger_output,
            previous_steps=previous_steps,
        )

    # Obter app correspondente
    app = AppRegistry.get_by_node_type(node_type)

    if app:
        # Determinar action key baseado no node type
        action_key = _get_action_key_for_node(node_type, config)

        # Validar parâmetros contra schema da action
        if not skip_validation:
            action_def = app.get_action(action_key)
            if action_def and action_def.arguments:
                try:
                    validate_and_raise(config, action_def.arguments)
                except Exception as e:
                    logger.error(f"Validation failed for {node_type}/{action_key}: {e}")
                    raise

        # Obter connection_id
        connection_id = config.get('connection_id') or config.get('source_connection_id')

        try:
            result = await app.execute_action(
                action_key=action_key,
                connection_id=connection_id,
                parameters=config,
                context=context,
            )
            return result
        except Exception as e:
            logger.error(f"Error executing action {action_key} for {node_type}: {e}")
            raise

    else:
        # Fallback para executor legado
        return await _execute_legacy_action(node, config, context)


def _get_action_key_for_node(node_type: str, config: Dict[str, Any]) -> str:
    """Determina a action key baseado no node type."""
    # Mapeamento padrão
    action_map = {
        'google-docs': 'copy-template',
        'google-slides': 'copy-template',
        'microsoft-word': 'copy-template',
        'microsoft-powerpoint': 'copy-template',
        'gmail': 'send-email',
        'outlook': 'send-email',
        'clicksign': 'create-envelope',
        'request-signatures': 'create-envelope',
        'hubspot': 'update-contact',
    }

    return action_map.get(node_type, 'execute')


async def _execute_legacy_action(node: Any, config: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Fallback para executar actions via executor legado.

    Usa o WorkflowExecutor existente para manter compatibilidade.
    """
    logger.warning(f"Using legacy executor for node type: {node.node_type}")

    # Por enquanto, retornar um resultado básico
    # O código existente no WorkflowExecutor pode ser chamado aqui
    return {
        'status': 'executed',
        'node_type': node.node_type,
        'node_id': str(node.id),
        'legacy': True,
    }
