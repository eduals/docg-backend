"""
Configurações do Temporal.
"""
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class TemporalConfig:
    """Configurações do Temporal Server"""
    
    # Endereço do Temporal Server (gRPC)
    address: str = os.getenv('TEMPORAL_ADDRESS', 'localhost:7233')
    
    # Namespace (default para desenvolvimento)
    namespace: str = os.getenv('TEMPORAL_NAMESPACE', 'default')
    
    # Task Queue para workflows DocG
    task_queue: str = os.getenv('TEMPORAL_TASK_QUEUE', 'docg-workflows')
    
    # Timeouts padrão (em segundos)
    default_activity_timeout: int = int(os.getenv('TEMPORAL_ACTIVITY_TIMEOUT', '300'))  # 5 min
    default_workflow_timeout: int = int(os.getenv('TEMPORAL_WORKFLOW_TIMEOUT', '86400'))  # 24h
    
    # Retry policy defaults
    max_activity_retries: int = int(os.getenv('TEMPORAL_MAX_RETRIES', '3'))
    initial_retry_interval_seconds: int = 1
    max_retry_interval_seconds: int = 60
    retry_backoff_coefficient: float = 2.0
    
    # Timeouts específicos por tipo de node
    trigger_timeout: int = 60  # 1 min
    document_timeout: int = 300  # 5 min
    email_timeout: int = 60  # 1 min
    signature_timeout: int = 120  # 2 min
    
    # Expiração padrão para approvals e signatures (em horas)
    default_approval_timeout_hours: int = 48
    default_signature_timeout_days: int = 7
    
    @classmethod
    def from_env(cls) -> 'TemporalConfig':
        """Cria config a partir de variáveis de ambiente"""
        return cls()


# Constantes para nomes de signals
class SignalNames:
    """Nomes dos signals usados nos workflows"""
    APPROVAL_DECISION = 'approval_decision'
    SIGNATURE_UPDATE = 'signature_update'


# Constantes para nomes de workflows
class WorkflowNames:
    """Nomes dos workflows"""
    DOCG_WORKFLOW = 'DocGWorkflow'


# Singleton da config
_config: Optional[TemporalConfig] = None


def get_config() -> TemporalConfig:
    """Retorna singleton da configuração"""
    global _config
    if _config is None:
        _config = TemporalConfig.from_env()
    return _config


