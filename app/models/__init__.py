# Importar models novos primeiro
from .organization import Organization, User, OrganizationFeature
from .connection import DataSourceConnection
from .template import Template
from .workflow import Workflow, WorkflowFieldMapping
from .document import GeneratedDocument
from .signature import SignatureRequest
from .execution import WorkflowExecution

# Importar models legados DEPOIS (para evitar importação circular)
# Usar importação lazy para evitar problemas
def _import_legacy():
    from .legacy import (
        FieldMapping,
        EnvelopeRelation,
        GoogleOAuthToken,
        GoogleDriveConfig,
        EnvelopeExecutionLog
    )
    return {
        'FieldMapping': FieldMapping,
        'EnvelopeRelation': EnvelopeRelation,
        'GoogleOAuthToken': GoogleOAuthToken,
        'GoogleDriveConfig': GoogleDriveConfig,
        'EnvelopeExecutionLog': EnvelopeExecutionLog
    }

# Importar agora
_legacy_models = _import_legacy()
FieldMapping = _legacy_models['FieldMapping']
EnvelopeRelation = _legacy_models['EnvelopeRelation']
GoogleOAuthToken = _legacy_models['GoogleOAuthToken']
GoogleDriveConfig = _legacy_models['GoogleDriveConfig']
EnvelopeExecutionLog = _legacy_models['EnvelopeExecutionLog']

# Importar RiscEvent do models.py principal (está definido lá, não em legacy)
# Usar import lazy para evitar circular
def _get_risc_event():
    # Importar apenas quando necessário
    import sys
    if 'app.models' in sys.modules:
        models_main = sys.modules['app.models']
        if hasattr(models_main, 'RiscEvent'):
            return models_main.RiscEvent
    # Se não encontrado, importar diretamente
    from app.models import RiscEvent
    return RiscEvent

# Criar propriedade lazy
class _RiscEventProxy:
    def __getattr__(self, name):
        return getattr(_get_risc_event(), name)

RiscEvent = _RiscEventProxy()

__all__ = [
    'Organization',
    'User',
    'OrganizationFeature',
    'DataSourceConnection',
    'Template',
    'Workflow',
    'WorkflowFieldMapping',
    'GeneratedDocument',
    'SignatureRequest',
    'WorkflowExecution',
    # Legacy models
    'FieldMapping',
    'EnvelopeRelation',
    'GoogleOAuthToken',
    'GoogleDriveConfig',
    'EnvelopeExecutionLog',
    'RiscEvent'
]

