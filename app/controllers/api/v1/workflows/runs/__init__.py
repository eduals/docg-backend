"""
Workflow Runs Controllers.
"""

from .list import list_workflow_runs
from .get import get_workflow_run

__all__ = [
    'list_workflow_runs',
    'get_workflow_run',
]
