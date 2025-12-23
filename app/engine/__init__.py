"""
DocG Engine - Sistema de Execução de Workflows

Este módulo contém a engine centralizada para execução de workflows,
seguindo os padrões arquiteturais do Automatisch.

Componentes principais:
- Engine: Classe principal de orquestração
- GlobalVariable: Sistema de contexto $ passado entre steps (legado)
- ExecutionContext: Novo contexto padronizado ($) - estilo Automatisch
- compute_parameters: Substituição de variáveis {{step.id.field}}
- Flow Context: Construção de contexto de workflow
- Action/Trigger Processors: Processamento de steps
- Steps Iterator: Iteração sequencial de steps

Uso:
    from app.engine import Engine, ExecutionContext

    # Executar workflow
    engine = Engine()
    result = await engine.run(workflow_id, trigger_data)

    # Usar compute_parameters
    from app.engine import compute_parameters
    params = compute_parameters(params, execution_id, trigger_output, previous_steps)

    # Construir ExecutionContext
    from app.engine import build_execution_context
    ctx = await build_execution_context(app_key='hubspot', ...)
"""

# Legado: GlobalVariable (será deprecado)
from .global_variable import GlobalVariable
from .global_variable import AuthContext as LegacyAuthContext
from .global_variable import FlowContext as LegacyFlowContext
from .global_variable import StepContext as LegacyStepContext
from .global_variable import ExecutionContext as LegacyExecutionContext

# Novo: ExecutionContext do base.py
from app.apps.base import (
    ExecutionContext,
    AuthContext,
    AppContext,
    FlowContext,
    StepContext,
    ExecutionMetadata,
    TriggerOutput,
    ActionOutput,
    Datastore,
    EarlyExitError,
    ActionResult,
    ActionArgument,
    ArgumentType,
    DynamicDataSource,
    DynamicFieldsSource,
)

# Context Builder
from .context import build_execution_context, build_context_from_execution

# Core
from .compute_parameters import compute_parameters, extract_variables
from .engine import Engine

__all__ = [
    # Main classes
    'Engine',
    'GlobalVariable',  # Legado

    # Novo: ExecutionContext e componentes
    'ExecutionContext',
    'AuthContext',
    'AppContext',
    'FlowContext',
    'StepContext',
    'ExecutionMetadata',
    'TriggerOutput',
    'ActionOutput',
    'Datastore',
    'EarlyExitError',

    # Action/Trigger helpers
    'ActionResult',
    'ActionArgument',
    'ArgumentType',
    'DynamicDataSource',
    'DynamicFieldsSource',

    # Context builders
    'build_execution_context',
    'build_context_from_execution',

    # Functions
    'compute_parameters',
    'extract_variables',
]
