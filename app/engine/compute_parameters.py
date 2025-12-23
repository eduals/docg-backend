"""
Compute Parameters System - Substituição de variáveis entre steps.

Similar ao computeParameters do Automatisch, este módulo substitui
variáveis no formato {{step.{stepId}.{keyPath}}} usando dados de
ExecutionSteps anteriores.

Formatos suportados:
- {{step.{stepId}.{keyPath}}} - Valor de um step anterior
- {{trigger.{keyPath}}} - Valor do trigger output
- {{flow.{keyPath}}} - Valor do flow context
- {{execution.{keyPath}}} - Valor do execution context
- {{env.{VAR_NAME}}} - Variável de ambiente
- {{now}} - Data/hora atual ISO
- {{uuid}} - UUID aleatório
"""

import re
import os
import uuid as uuid_lib
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
from app.models.execution_step import ExecutionStep


# Regex para encontrar variáveis no formato {{...}}
VARIABLE_PATTERN = re.compile(r'\{\{([^}]+)\}\}')

# Regex específico para step variables
STEP_VARIABLE_PATTERN = re.compile(r'^step\.([^.]+)\.(.+)$')


def compute_parameters(
    parameters: Union[Dict[str, Any], List, str, Any],
    execution_id: str = None,
    trigger_output: Dict[str, Any] = None,
    flow_context: Dict[str, Any] = None,
    execution_context: Dict[str, Any] = None,
    previous_steps: List[ExecutionStep] = None,
    env_vars: Dict[str, str] = None,
) -> Union[Dict[str, Any], List, str, Any]:
    """
    Substitui variáveis nos parâmetros usando dados de steps anteriores.

    Args:
        parameters: Parâmetros a processar (dict, list, string ou valor primitivo)
        execution_id: ID da execução (para buscar steps do banco)
        trigger_output: Output do trigger step
        flow_context: Contexto do workflow
        execution_context: Contexto da execução
        previous_steps: Lista de ExecutionSteps anteriores (opcional, será buscado se não fornecido)
        env_vars: Variáveis de ambiente (opcional, usa os.environ se não fornecido)

    Returns:
        Parâmetros com variáveis substituídas
    """
    # Preparar contexto de substituição
    context = _build_substitution_context(
        execution_id=execution_id,
        trigger_output=trigger_output,
        flow_context=flow_context,
        execution_context=execution_context,
        previous_steps=previous_steps,
        env_vars=env_vars,
    )

    return _substitute_recursive(parameters, context)


def _build_substitution_context(
    execution_id: str = None,
    trigger_output: Dict[str, Any] = None,
    flow_context: Dict[str, Any] = None,
    execution_context: Dict[str, Any] = None,
    previous_steps: List[ExecutionStep] = None,
    env_vars: Dict[str, str] = None,
) -> Dict[str, Any]:
    """
    Constrói o contexto de substituição com todos os dados disponíveis.

    Returns:
        Dicionário com dados para substituição
    """
    # Buscar steps anteriores do banco se não fornecidos
    step_outputs = {}
    if previous_steps:
        for step in previous_steps:
            if step.data_out:
                step_outputs[str(step.step_id)] = step.data_out
    elif execution_id:
        # Buscar do banco
        steps = ExecutionStep.get_by_execution(execution_id, status='success')
        for step in steps:
            if step.data_out:
                step_outputs[str(step.step_id)] = step.data_out

    return {
        'step': step_outputs,
        'trigger': trigger_output or {},
        'flow': flow_context or {},
        'execution': execution_context or {},
        'env': env_vars or dict(os.environ),
    }


def _substitute_recursive(
    value: Union[Dict[str, Any], List, str, Any],
    context: Dict[str, Any],
) -> Union[Dict[str, Any], List, str, Any]:
    """
    Recursivamente substitui variáveis em estruturas aninhadas.

    Args:
        value: Valor a processar
        context: Contexto de substituição

    Returns:
        Valor com variáveis substituídas
    """
    if isinstance(value, str):
        return _substitute_string(value, context)
    elif isinstance(value, dict):
        return {k: _substitute_recursive(v, context) for k, v in value.items()}
    elif isinstance(value, list):
        return [_substitute_recursive(item, context) for item in value]
    else:
        # Valores primitivos (int, float, bool, None) retornam como estão
        return value


def _substitute_string(text: str, context: Dict[str, Any]) -> Union[str, Any]:
    """
    Substitui variáveis em uma string.

    Se a string inteira for uma variável (ex: "{{step.abc.field}}"),
    retorna o valor original (pode ser dict, list, etc).

    Se a string contém múltiplas variáveis ou texto misto,
    retorna uma string com as variáveis substituídas.

    Args:
        text: String com variáveis
        context: Contexto de substituição

    Returns:
        String ou valor original
    """
    # Verificar se é uma variável única (toda a string)
    match = VARIABLE_PATTERN.fullmatch(text.strip())
    if match:
        key_path = match.group(1).strip()
        value = _resolve_variable(key_path, context)
        # Retorna o valor original (pode ser dict, list, etc)
        return value if value is not None else text

    # String com múltiplas variáveis ou texto misto
    def replace_match(m):
        key_path = m.group(1).strip()
        value = _resolve_variable(key_path, context)
        if value is None:
            return m.group(0)  # Mantém a variável original se não encontrada
        return str(value)

    return VARIABLE_PATTERN.sub(replace_match, text)


def _resolve_variable(key_path: str, context: Dict[str, Any]) -> Any:
    """
    Resolve uma variável pelo seu key path.

    Formatos suportados:
    - step.{stepId}.{keyPath}
    - trigger.{keyPath}
    - flow.{keyPath}
    - execution.{keyPath}
    - env.{VAR_NAME}
    - now
    - uuid

    Args:
        key_path: Caminho da variável
        context: Contexto de substituição

    Returns:
        Valor resolvido ou None
    """
    parts = key_path.split('.')

    if not parts:
        return None

    root = parts[0]

    # Variáveis especiais
    if root == 'now':
        return datetime.utcnow().isoformat()
    elif root == 'uuid':
        return str(uuid_lib.uuid4())

    # Step variable: step.{stepId}.{keyPath}
    if root == 'step' and len(parts) >= 3:
        step_id = parts[1]
        step_outputs = context.get('step', {})
        step_data = step_outputs.get(step_id)
        if step_data:
            return _get_nested_value(step_data, parts[2:])
        return None

    # Trigger variable: trigger.{keyPath}
    elif root == 'trigger':
        trigger_data = context.get('trigger', {})
        return _get_nested_value(trigger_data, parts[1:])

    # Flow variable: flow.{keyPath}
    elif root == 'flow':
        flow_data = context.get('flow', {})
        return _get_nested_value(flow_data, parts[1:])

    # Execution variable: execution.{keyPath}
    elif root == 'execution':
        execution_data = context.get('execution', {})
        return _get_nested_value(execution_data, parts[1:])

    # Environment variable: env.{VAR_NAME}
    elif root == 'env' and len(parts) >= 2:
        env_vars = context.get('env', {})
        var_name = '.'.join(parts[1:])  # Suporta nomes com pontos
        return env_vars.get(var_name)

    return None


def _get_nested_value(obj: Any, keys: List[str]) -> Any:
    """
    Obtém valor aninhado de um objeto usando lista de chaves.

    Args:
        obj: Objeto (dict ou list)
        keys: Lista de chaves/índices

    Returns:
        Valor encontrado ou None
    """
    if not keys:
        return obj

    for key in keys:
        if obj is None:
            return None
        elif isinstance(obj, dict):
            obj = obj.get(key)
        elif isinstance(obj, list):
            try:
                index = int(key)
                obj = obj[index]
            except (ValueError, IndexError):
                return None
        else:
            # Tenta acessar atributo
            try:
                obj = getattr(obj, key, None)
            except Exception:
                return None

    return obj


def extract_variables(text: str) -> List[str]:
    """
    Extrai todas as variáveis de uma string.

    Args:
        text: String com variáveis

    Returns:
        Lista de key paths das variáveis encontradas
    """
    if not isinstance(text, str):
        return []

    matches = VARIABLE_PATTERN.findall(text)
    return [m.strip() for m in matches]


def extract_step_references(parameters: Union[Dict, List, str, Any]) -> List[str]:
    """
    Extrai todos os step IDs referenciados nos parâmetros.

    Útil para determinar dependências entre steps.

    Args:
        parameters: Parâmetros a analisar

    Returns:
        Lista de step IDs únicos referenciados
    """
    step_ids = set()

    def extract_from_value(value):
        if isinstance(value, str):
            for var in extract_variables(value):
                match = STEP_VARIABLE_PATTERN.match(var)
                if match:
                    step_ids.add(match.group(1))
        elif isinstance(value, dict):
            for v in value.values():
                extract_from_value(v)
        elif isinstance(value, list):
            for item in value:
                extract_from_value(item)

    extract_from_value(parameters)
    return list(step_ids)


def validate_parameters(
    parameters: Union[Dict, List, str, Any],
    available_steps: List[str] = None,
) -> Dict[str, Any]:
    """
    Valida que todas as variáveis de step referenciadas existem.

    Args:
        parameters: Parâmetros a validar
        available_steps: Lista de step IDs disponíveis

    Returns:
        Dict com 'valid' (bool) e 'missing_steps' (list de IDs não encontrados)
    """
    referenced_steps = extract_step_references(parameters)
    available_steps = available_steps or []

    missing_steps = [
        step_id for step_id in referenced_steps
        if step_id not in available_steps
    ]

    return {
        'valid': len(missing_steps) == 0,
        'missing_steps': missing_steps,
        'referenced_steps': referenced_steps,
    }


# Classe helper para uso fluente
class ParameterComputer:
    """
    Helper class para computar parâmetros com contexto pré-definido.

    Exemplo:
        computer = ParameterComputer(execution_id='abc')
        computer.set_trigger_output({'contact': {'id': '123'}})
        result = computer.compute({'email': '{{trigger.contact.email}}'})
    """

    def __init__(
        self,
        execution_id: str = None,
        trigger_output: Dict[str, Any] = None,
        flow_context: Dict[str, Any] = None,
        execution_context: Dict[str, Any] = None,
    ):
        self.execution_id = execution_id
        self.trigger_output = trigger_output or {}
        self.flow_context = flow_context or {}
        self.execution_context = execution_context or {}
        self._step_outputs: Dict[str, Dict[str, Any]] = {}

    def set_trigger_output(self, output: Dict[str, Any]):
        """Define o output do trigger"""
        self.trigger_output = output

    def add_step_output(self, step_id: str, output: Dict[str, Any]):
        """Adiciona output de um step"""
        self._step_outputs[step_id] = output

    def compute(self, parameters: Any) -> Any:
        """Computa parâmetros usando o contexto definido"""
        # Criar ExecutionSteps fake para o contexto
        class FakeStep:
            def __init__(self, step_id, data_out):
                self.step_id = step_id
                self.data_out = data_out

        previous_steps = [
            FakeStep(sid, out) for sid, out in self._step_outputs.items()
        ]

        return compute_parameters(
            parameters=parameters,
            execution_id=self.execution_id,
            trigger_output=self.trigger_output,
            flow_context=self.flow_context,
            execution_context=self.execution_context,
            previous_steps=previous_steps,
        )
