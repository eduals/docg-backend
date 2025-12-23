"""
Compute Parameters System - Substituição de variáveis entre steps.

Similar ao computeParameters do Automatisch, este módulo substitui
variáveis no formato {{step.{stepId}.{keyPath}}} usando dados de
ExecutionSteps anteriores.

Formatos suportados (modo básico):
- {{step.{stepId}.{keyPath}}} - Valor de um step anterior
- {{trigger.{keyPath}}} - Valor do trigger output
- {{flow.{keyPath}}} - Valor do flow context
- {{execution.{keyPath}}} - Valor do execution context
- {{env.{VAR_NAME}}} - Variável de ambiente
- {{now}} - Data/hora atual ISO
- {{uuid}} - UUID aleatório

Formatos adicionais (modo avançado - use_advanced_tags=True):
- {{value | format:"DD/MM/YYYY"}} - Pipes/transforms
- {{= expression}} - Fórmulas matemáticas
- {{IF condition}}...{{ELSE}}...{{ENDIF}} - Condicionais
- {{FOR item IN collection}}...{{ENDFOR}} - Loops
- {{$timestamp}}, {{$date}}, {{$uuid}} - Variáveis globais
"""

import re
import os
import uuid as uuid_lib
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
from app.models.execution_step import ExecutionStep
import logging

logger = logging.getLogger(__name__)


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
    use_advanced_tags: bool = False,
    trigger_source: str = 'generic',
    workflow_metadata: Dict[str, Any] = None,
    locale: str = 'pt_BR',
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
        use_advanced_tags: Se True, usa o sistema avançado de tags com pipes, fórmulas, etc.
        trigger_source: Identificador da fonte (hubspot, webhook, etc.) para normalização
        workflow_metadata: Metadados do workflow (nome, id)
        locale: Locale para formatação (default: pt_BR)

    Returns:
        Parâmetros com variáveis substituídas
    """
    # Se usar tags avançadas, delega para o novo sistema
    if use_advanced_tags:
        return _compute_with_advanced_tags(
            parameters=parameters,
            execution_id=execution_id,
            trigger_output=trigger_output,
            flow_context=flow_context,
            execution_context=execution_context,
            previous_steps=previous_steps,
            env_vars=env_vars,
            trigger_source=trigger_source,
            workflow_metadata=workflow_metadata,
            locale=locale,
        )

    # Modo básico: preparar contexto de substituição
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


def _compute_with_advanced_tags(
    parameters: Union[Dict[str, Any], List, str, Any],
    execution_id: str = None,
    trigger_output: Dict[str, Any] = None,
    flow_context: Dict[str, Any] = None,
    execution_context: Dict[str, Any] = None,
    previous_steps: List[ExecutionStep] = None,
    env_vars: Dict[str, str] = None,
    trigger_source: str = 'generic',
    workflow_metadata: Dict[str, Any] = None,
    locale: str = 'pt_BR',
) -> Union[Dict[str, Any], List, str, Any]:
    """
    Processa parâmetros usando o sistema avançado de tags.

    Suporta:
    - Pipes/transforms: {{value | format:"DD/MM/YYYY"}}
    - Fórmulas: {{= expression}}
    - Condicionais: {{IF condition}}...{{ELSE}}...{{ENDIF}}
    - Loops: {{FOR item IN collection}}...{{ENDFOR}}
    - Variáveis globais: {{$timestamp}}, {{$date}}, etc.

    Args:
        parameters: Parâmetros a processar
        execution_id: ID da execução
        trigger_output: Output do trigger
        flow_context: Contexto do workflow
        execution_context: Contexto da execução
        previous_steps: Steps anteriores
        env_vars: Variáveis de ambiente
        trigger_source: Fonte do trigger (hubspot, webhook, etc.)
        workflow_metadata: Metadados do workflow
        locale: Locale para formatação

    Returns:
        Parâmetros processados
    """
    try:
        # Importar o sistema de tags avançado
        from app.tags.context.builder import ContextBuilder

        # Construir lista de previous steps no formato esperado
        previous_steps_list = []
        if previous_steps:
            for step in previous_steps:
                if step.data_out:
                    previous_steps_list.append({
                        'step_id': str(step.step_id),
                        'node_id': str(step.node_id) if hasattr(step, 'node_id') else None,
                        'action_key': getattr(step, 'action_key', None),
                        'data_out': step.data_out
                    })
        elif execution_id:
            # Buscar do banco
            steps = ExecutionStep.get_by_execution(execution_id, status='success')
            for step in steps:
                if step.data_out:
                    previous_steps_list.append({
                        'step_id': str(step.step_id),
                        'node_id': str(step.node_id) if hasattr(step, 'node_id') else None,
                        'action_key': getattr(step, 'action_key', None),
                        'data_out': step.data_out
                    })

        # Construir contexto usando o ContextBuilder
        context_builder = ContextBuilder(locale=locale)
        context = context_builder.build(
            trigger_data=trigger_output,
            trigger_source=trigger_source,
            previous_steps=previous_steps_list,
            flow_context=flow_context,
            execution_context=execution_context,
            env_vars=env_vars or dict(os.environ),
            workflow_metadata=workflow_metadata
        )

        # Importar e usar o TagProcessor
        from app.tags import TagProcessor
        processor = TagProcessor(context=context, locale=locale)

        return processor.process(parameters)

    except Exception as e:
        logger.warning(f"Advanced tag processing failed, falling back to basic: {e}")
        # Fallback para o modo básico
        context = _build_substitution_context(
            execution_id=execution_id,
            trigger_output=trigger_output,
            flow_context=flow_context,
            execution_context=execution_context,
            previous_steps=previous_steps,
            env_vars=env_vars,
        )
        return _substitute_recursive(parameters, context)


def has_advanced_tag_syntax(text: str) -> bool:
    """
    Detecta se o texto contém sintaxe avançada de tags.

    Útil para auto-detectar quando usar o modo avançado.

    Args:
        text: Texto a analisar

    Returns:
        True se contém pipes, fórmulas, condicionais ou loops
    """
    if not isinstance(text, str):
        return False

    # Padrões de sintaxe avançada
    advanced_patterns = [
        r'\{\{[^}]+\|',           # Pipes: {{value | transform}}
        r'\{\{=',                  # Fórmulas: {{= expression}}
        r'\{\{IF\s',               # Condicionais: {{IF condition}}
        r'\{\{FOR\s',              # Loops: {{FOR item IN}}
        r'\{\{\$',                 # Variáveis globais: {{$timestamp}}
    ]

    for pattern in advanced_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True

    return False


def detect_and_compute(
    parameters: Union[Dict[str, Any], List, str, Any],
    execution_id: str = None,
    trigger_output: Dict[str, Any] = None,
    flow_context: Dict[str, Any] = None,
    execution_context: Dict[str, Any] = None,
    previous_steps: List[ExecutionStep] = None,
    env_vars: Dict[str, str] = None,
    trigger_source: str = 'generic',
    workflow_metadata: Dict[str, Any] = None,
    locale: str = 'pt_BR',
) -> Union[Dict[str, Any], List, str, Any]:
    """
    Auto-detecta se deve usar tags avançadas e processa.

    Verifica o conteúdo e usa o modo avançado se detectar
    sintaxe como pipes, fórmulas, condicionais ou loops.

    Args:
        parameters: Parâmetros a processar
        (demais argumentos iguais a compute_parameters)

    Returns:
        Parâmetros processados
    """
    # Verificar se precisa de tags avançadas
    use_advanced = False

    def check_value(value):
        nonlocal use_advanced
        if use_advanced:
            return
        if isinstance(value, str):
            if has_advanced_tag_syntax(value):
                use_advanced = True
        elif isinstance(value, dict):
            for v in value.values():
                check_value(v)
        elif isinstance(value, list):
            for item in value:
                check_value(item)

    check_value(parameters)

    return compute_parameters(
        parameters=parameters,
        execution_id=execution_id,
        trigger_output=trigger_output,
        flow_context=flow_context,
        execution_context=execution_context,
        previous_steps=previous_steps,
        env_vars=env_vars,
        use_advanced_tags=use_advanced,
        trigger_source=trigger_source,
        workflow_metadata=workflow_metadata,
        locale=locale,
    )


# Classe helper para uso fluente
class ParameterComputer:
    """
    Helper class para computar parâmetros com contexto pré-definido.

    Exemplo:
        computer = ParameterComputer(execution_id='abc')
        computer.set_trigger_output({'contact': {'id': '123'}})
        result = computer.compute({'email': '{{trigger.contact.email}}'})

    Para tags avançadas:
        computer = ParameterComputer(use_advanced_tags=True, locale='pt_BR')
        computer.set_trigger_output({'deal': {'amount': 50000}})
        result = computer.compute('Total: {{trigger.deal.amount | currency:"BRL"}}')
    """

    def __init__(
        self,
        execution_id: str = None,
        trigger_output: Dict[str, Any] = None,
        flow_context: Dict[str, Any] = None,
        execution_context: Dict[str, Any] = None,
        use_advanced_tags: bool = False,
        trigger_source: str = 'generic',
        workflow_metadata: Dict[str, Any] = None,
        locale: str = 'pt_BR',
    ):
        self.execution_id = execution_id
        self.trigger_output = trigger_output or {}
        self.flow_context = flow_context or {}
        self.execution_context = execution_context or {}
        self._step_outputs: Dict[str, Dict[str, Any]] = {}
        self.use_advanced_tags = use_advanced_tags
        self.trigger_source = trigger_source
        self.workflow_metadata = workflow_metadata or {}
        self.locale = locale

    def set_trigger_output(self, output: Dict[str, Any]):
        """Define o output do trigger"""
        self.trigger_output = output

    def set_trigger_source(self, source: str):
        """Define a fonte do trigger (hubspot, webhook, etc.)"""
        self.trigger_source = source

    def set_workflow_metadata(self, metadata: Dict[str, Any]):
        """Define metadados do workflow"""
        self.workflow_metadata = metadata

    def add_step_output(self, step_id: str, output: Dict[str, Any]):
        """Adiciona output de um step"""
        self._step_outputs[step_id] = output

    def compute(self, parameters: Any, auto_detect: bool = False) -> Any:
        """
        Computa parâmetros usando o contexto definido.

        Args:
            parameters: Parâmetros a processar
            auto_detect: Se True, auto-detecta se deve usar tags avançadas

        Returns:
            Parâmetros processados
        """
        # Criar ExecutionSteps fake para o contexto
        class FakeStep:
            def __init__(self, step_id, data_out):
                self.step_id = step_id
                self.data_out = data_out

        previous_steps = [
            FakeStep(sid, out) for sid, out in self._step_outputs.items()
        ]

        if auto_detect:
            return detect_and_compute(
                parameters=parameters,
                execution_id=self.execution_id,
                trigger_output=self.trigger_output,
                flow_context=self.flow_context,
                execution_context=self.execution_context,
                previous_steps=previous_steps,
                trigger_source=self.trigger_source,
                workflow_metadata=self.workflow_metadata,
                locale=self.locale,
            )

        return compute_parameters(
            parameters=parameters,
            execution_id=self.execution_id,
            trigger_output=self.trigger_output,
            flow_context=self.flow_context,
            execution_context=self.execution_context,
            previous_steps=previous_steps,
            use_advanced_tags=self.use_advanced_tags,
            trigger_source=self.trigger_source,
            workflow_metadata=self.workflow_metadata,
            locale=self.locale,
        )
