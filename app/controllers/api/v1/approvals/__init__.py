"""
Approvals Controllers.

Controllers para gerenciamento de aprovações de workflow.
"""

from .get import get_approval_status
from .approve import approve_workflow
from .reject import reject_workflow
from .list import list_workflow_approvals

# Aliases para compatibilidade
get_approval = get_approval_status
approve_approval = approve_workflow
reject_approval = reject_workflow

__all__ = [
    'get_approval_status',
    'approve_workflow',
    'reject_workflow',
    'list_workflow_approvals',
    # Aliases
    'get_approval',
    'approve_approval',
    'reject_approval',
]
