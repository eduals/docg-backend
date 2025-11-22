"""
Models legados importados do arquivo models.py original.
Mantido para compatibilidade com código existente.
"""
# Importar models do arquivo models.py original (no mesmo diretório app)
# Usar importação direta do arquivo para evitar importação circular
import importlib.util
import os

# Caminho para o arquivo models.py original
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
models_file = os.path.join(parent_dir, 'models.py')

# Carregar módulo dinamicamente com um nome único para evitar conflitos
spec = importlib.util.spec_from_file_location("_legacy_models_file", models_file)
legacy_models = importlib.util.module_from_spec(spec)

# Adicionar db ao namespace do módulo antes de executar
# Isso evita erros de importação
from app.database import db
legacy_models.db = db

# Executar o módulo
spec.loader.exec_module(legacy_models)

# Exportar classes
# Account foi removido - migrado para Organization
FieldMapping = legacy_models.FieldMapping
EnvelopeRelation = legacy_models.EnvelopeRelation
GoogleOAuthToken = legacy_models.GoogleOAuthToken
GoogleDriveConfig = legacy_models.GoogleDriveConfig
EnvelopeExecutionLog = legacy_models.EnvelopeExecutionLog

__all__ = [
    'FieldMapping',
    'EnvelopeRelation',
    'GoogleOAuthToken',
    'GoogleDriveConfig',
    'EnvelopeExecutionLog'
]
