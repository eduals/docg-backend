"""
Serializers - Transformam models em dicionários para respostas da API.

Seguindo padrão do Automatisch, serializers centralizam a lógica de
transformação de objetos do banco para JSON da API.

Benefícios:
- Consistência nas respostas
- Controle de quais campos são expostos
- Transformações e formatações centralizadas
- Facilita versionamento da API
"""

from .workflow_serializer import WorkflowSerializer
from .template_serializer import TemplateSerializer
from .document_serializer import DocumentSerializer
from .connection_serializer import ConnectionSerializer
from .organization_serializer import OrganizationSerializer
from .user_serializer import UserSerializer
from .execution_serializer import ExecutionSerializer
from .approval_serializer import ApprovalSerializer
from .signature_serializer import SignatureSerializer
from .node_serializer import NodeSerializer

__all__ = [
    'WorkflowSerializer',
    'TemplateSerializer',
    'DocumentSerializer',
    'ConnectionSerializer',
    'OrganizationSerializer',
    'UserSerializer',
    'ExecutionSerializer',
    'ApprovalSerializer',
    'SignatureSerializer',
    'NodeSerializer',
]
