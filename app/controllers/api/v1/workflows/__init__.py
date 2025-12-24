"""
Workflows Controllers - DEPRECATED

⚠️ ATENÇÃO: Este módulo foi deprecated durante a migração JSONB.

Todos os endpoints de workflows foram movidos para:
- app/routes/workflows.py (endpoints principais de CRUD)

Arquivos deletados durante migração:
- list.py, get.py, create.py, update.py, delete.py
- activate.py, preview.py
- nodes/, ai_mappings/, field_mappings/, runs/

Arquivos mantidos:
- helpers.py (helpers utilitários)
- tags_preview.py (preview de tags)

Para acessar funcionalidades de workflow, use app/routes/workflows.py
"""

# Import apenas helpers que ainda existem
from .helpers import workflow_to_dict, validate_post_actions

__all__ = [
    'workflow_to_dict',
    'validate_post_actions',
]
