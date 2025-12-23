"""
Execution Phases - Define as fases de execução de um workflow.

Este módulo define as fases pelas quais uma execução de workflow pode passar,
permitindo controle granular sobre dry-run e until_phase.
"""

from enum import Enum
from typing import Optional


class ExecutionPhase(str, Enum):
    """
    Fases de execução de um workflow.

    Ordem sequencial:
    1. PREFLIGHT - Validações pré-execução
    2. TRIGGER - Extração de dados do trigger
    3. RENDER - Geração de documentos
    4. SAVE - Persistência de documentos (Drive, Storage)
    5. DELIVERY - Envio de emails
    6. SIGNATURE - Coleta de assinaturas digitais
    """
    PREFLIGHT = 'preflight'
    TRIGGER = 'trigger'
    RENDER = 'render'
    SAVE = 'save'
    DELIVERY = 'delivery'
    SIGNATURE = 'signature'


# Ordem das fases (usado para comparação)
PHASE_ORDER = [
    ExecutionPhase.PREFLIGHT,
    ExecutionPhase.TRIGGER,
    ExecutionPhase.RENDER,
    ExecutionPhase.SAVE,
    ExecutionPhase.DELIVERY,
    ExecutionPhase.SIGNATURE,
]


def should_stop_at_phase(
    current_phase: ExecutionPhase,
    until_phase: Optional[str]
) -> bool:
    """
    Verifica se a execução deve parar na fase atual.

    Args:
        current_phase: Fase atual
        until_phase: Fase limite (opcional)

    Returns:
        True se deve parar, False caso contrário

    Examples:
        >>> should_stop_at_phase(ExecutionPhase.RENDER, 'render')
        True
        >>> should_stop_at_phase(ExecutionPhase.TRIGGER, 'render')
        False
        >>> should_stop_at_phase(ExecutionPhase.DELIVERY, 'render')
        True
    """
    if not until_phase:
        return False

    try:
        current_idx = PHASE_ORDER.index(current_phase)
        until_idx = PHASE_ORDER.index(ExecutionPhase(until_phase))

        # Para na fase especificada (inclusive)
        return current_idx >= until_idx
    except (ValueError, KeyError):
        # Se until_phase inválido, não para
        return False


def get_phase_index(phase: ExecutionPhase) -> int:
    """
    Retorna o índice da fase na ordem de execução.

    Args:
        phase: Fase

    Returns:
        Índice (0-5)
    """
    return PHASE_ORDER.index(phase)
