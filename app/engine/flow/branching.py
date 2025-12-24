"""
Lógica de branching desacoplada do model.

Funções puras para avaliar condições de branching sem depender de WorkflowNode model.
"""
from typing import Dict, Any, Optional, List


def is_branch_node(node: Dict[str, Any]) -> bool:
    """
    Verifica se um node tem branching (múltiplas saídas condicionais).

    Args:
        node: Node dict com structural_type

    Returns:
        True se é um branch node
    """
    return node.get('structural_type') == 'branch'


def evaluate_branch_conditions(
    node: Dict[str, Any],
    context: dict,
    previous_steps: list
) -> Optional[str]:
    """
    Avalia branch conditions e retorna o ID do próximo node.

    Args:
        node: Node dict com branch_conditions
        context: Contexto de execução (trigger_data, etc)
        previous_steps: Steps anteriores executados

    Returns:
        ID do próximo node ou None se nenhuma condition match
    """
    branch_conditions = node.get('branch_conditions', [])

    if not branch_conditions:
        return None

    for branch in branch_conditions:
        conditions = branch.get('conditions')
        next_node_id = branch.get('next_node_id')

        # Default path (conditions == None) - sempre executado se nenhum outro match
        if conditions is None:
            return next_node_id

        # Avaliar condições
        if _evaluate_conditions(conditions, context, previous_steps):
            return next_node_id

    return None


def _evaluate_conditions(
    conditions: Dict[str, Any],
    context: dict,
    previous_steps: list
) -> bool:
    """
    Avalia um grupo de condições (AND/OR).

    Args:
        conditions: {
            'type': 'and' ou 'or',
            'rules': [
                {'field': '{{step.x.y}}', 'operator': '>', 'value': 100},
                ...
            ]
        }
        context: Contexto de execução
        previous_steps: Steps anteriores

    Returns:
        True se condições são satisfeitas
    """
    rules = conditions.get('rules', [])
    condition_type = conditions.get('type', 'and')

    if not rules:
        return True

    results = []
    for rule in rules:
        field = rule.get('field', '')
        operator = rule.get('operator', '==')
        expected = rule.get('value')

        # Resolver variável {{step.x.y}} ou {{trigger.field}}
        actual = _resolve_variable(field, context, previous_steps)

        # Comparar
        result = _compare_values(actual, operator, expected)
        results.append(result)

    # AND: todos devem ser True
    # OR: pelo menos um deve ser True
    if condition_type == 'and':
        return all(results)
    return any(results)


def _resolve_variable(field: str, context: dict, previous_steps: list) -> Any:
    """
    Resolve variáveis no formato {{step.x.y}} ou {{trigger.field}}.

    Examples:
        {{step.node-1.amount}} → previous_steps['node-1'].data_out['amount']
        {{trigger.deal.name}} → context['trigger_data']['deal']['name']

    Args:
        field: String com possível variável
        context: Contexto de execução
        previous_steps: Steps anteriores

    Returns:
        Valor resolvido ou field original se não for variável
    """
    if '{{' not in field:
        return field

    # Extrair path entre {{ e }}
    match = field.replace('{{', '').replace('}}', '').strip()
    parts = match.split('.')

    if not parts:
        return field

    # {{step.nodeId.field.path}}
    if parts[0] == 'step' and len(parts) >= 3:
        node_id = parts[1]

        # Buscar output do step
        for step in previous_steps:
            if isinstance(step, dict) and step.get('id') == node_id:
                # step é um dict (normalizado)
                return _get_nested(step.get('data_out', {}), parts[2:])
            elif hasattr(step, 'id') and str(step.id) == node_id:
                # step é um ExecutionStep object
                return _get_nested(step.data_out or {}, parts[2:])

        return None

    # {{trigger.field.path}}
    elif parts[0] == 'trigger':
        trigger_data = context.get('trigger_data', {})
        return _get_nested(trigger_data, parts[1:])

    return field


def _get_nested(obj: Any, keys: List[str]) -> Any:
    """
    Obtém valor aninhado de um objeto usando lista de chaves.

    Examples:
        _get_nested({'a': {'b': 1}}, ['a', 'b']) → 1
        _get_nested([{'x': 1}, {'x': 2}], ['0', 'x']) → 1

    Args:
        obj: Objeto (dict ou list)
        keys: Lista de chaves/índices

    Returns:
        Valor encontrado ou None
    """
    for key in keys:
        if isinstance(obj, dict):
            obj = obj.get(key)
        elif isinstance(obj, list):
            try:
                index = int(key)
                obj = obj[index]
            except (ValueError, IndexError):
                return None
        else:
            return None

        if obj is None:
            return None

    return obj


def _compare_values(actual: Any, operator: str, expected: Any) -> bool:
    """
    Compara dois valores usando um operador.

    Operadores suportados:
        ==, !=, >, <, >=, <=,
        contains, not_contains,
        starts_with, ends_with,
        is_empty, is_not_empty

    Args:
        actual: Valor real (resolvido de variável)
        operator: Operador de comparação
        expected: Valor esperado

    Returns:
        True se comparação satisfeita
    """
    try:
        if operator == '==':
            return str(actual) == str(expected)
        elif operator == '!=':
            return str(actual) != str(expected)
        elif operator == '>':
            return float(actual) > float(expected)
        elif operator == '<':
            return float(actual) < float(expected)
        elif operator == '>=':
            return float(actual) >= float(expected)
        elif operator == '<=':
            return float(actual) <= float(expected)
        elif operator == 'contains':
            return str(expected) in str(actual)
        elif operator == 'not_contains':
            return str(expected) not in str(actual)
        elif operator == 'starts_with':
            return str(actual).startswith(str(expected))
        elif operator == 'ends_with':
            return str(actual).endswith(str(expected))
        elif operator == 'is_empty':
            return not actual or actual == '' or actual == [] or actual == {}
        elif operator == 'is_not_empty':
            return bool(actual) and actual != '' and actual != [] and actual != {}
        else:
            return False
    except (ValueError, TypeError):
        return False
