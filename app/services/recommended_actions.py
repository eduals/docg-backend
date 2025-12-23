"""
RecommendedActions Service - Gera CTAs para resolver issues.

Feature 13: Recommended Actions
"""
from typing import List, Dict
from dataclasses import dataclass, asdict


@dataclass
class RecommendedAction:
    """Ação recomendada para resolver um issue"""
    action: str          # fix_permissions, select_folder, map_fields, reconnect_provider, retry
    label: str           # "Corrigir permissões"
    description: str     # "Conceda acesso de leitura ao arquivo"
    target_node_id: str  # UUID do node com problema
    params: Dict         # Parâmetros extras

    def to_dict(self):
        return asdict(self)


# === Mapeamento de códigos de erro para ações ===

ACTION_MAPPINGS = {
    # Permissões
    'drive.insufficient_permissions': {
        'action': 'fix_permissions',
        'label': 'Corrigir permissões',
        'description': 'Conceda acesso de leitura ao arquivo',
    },
    'drive.folder_not_found': {
        'action': 'select_folder',
        'label': 'Selecionar pasta',
        'description': 'A pasta de destino não existe mais',
    },
    'onedrive.insufficient_permissions': {
        'action': 'fix_permissions',
        'label': 'Corrigir permissões',
        'description': 'Conceda permissões necessárias no OneDrive',
    },

    # Dados
    'unresolved_variables': {
        'action': 'map_fields',
        'label': 'Mapear campos',
        'description': 'Algumas variáveis não foram resolvidas',
    },
    'missing_required_field': {
        'action': 'fill_required',
        'label': 'Preencher campos',
        'description': 'Campos obrigatórios estão vazios',
    },
    'invalid_field_format': {
        'action': 'fix_field_format',
        'label': 'Corrigir formato',
        'description': 'Alguns campos estão em formato inválido',
    },

    # Conexões
    'oauth_expired': {
        'action': 'reconnect_provider',
        'label': 'Reconectar',
        'description': 'A conexão OAuth expirou',
    },
    'oauth_revoked': {
        'action': 'reconnect_provider',
        'label': 'Reconectar',
        'description': 'A conexão foi revogada, reconecte para continuar',
    },
    'connection_error': {
        'action': 'reconnect_provider',
        'label': 'Verificar conexão',
        'description': 'Erro ao conectar com o serviço',
    },
    'api_key_invalid': {
        'action': 'update_api_key',
        'label': 'Atualizar API Key',
        'description': 'A API Key é inválida',
    },

    # Template
    'template_not_found': {
        'action': 'select_template',
        'label': 'Selecionar template',
        'description': 'O template não foi encontrado',
    },
    'template_invalid_tags': {
        'action': 'fix_template_tags',
        'label': 'Corrigir tags',
        'description': 'O template contém tags inválidas',
    },

    # Transient (retry)
    'rate_limit': {
        'action': 'retry',
        'label': 'Tentar novamente',
        'description': 'Limite de requisições atingido, tente em alguns minutos',
    },
    'timeout': {
        'action': 'retry',
        'label': 'Tentar novamente',
        'description': 'Tempo limite excedido',
    },
    'service_unavailable': {
        'action': 'retry',
        'label': 'Tentar novamente',
        'description': 'Serviço temporariamente indisponível',
    },
}


def get_recommended_actions(issues: List[Dict]) -> List[RecommendedAction]:
    """
    Gera ações recomendadas baseadas em issues do preflight.

    Args:
        issues: Lista de PreflightIssue dicts com estrutura:
            {
                'code': 'drive.insufficient_permissions',
                'domain': 'permissions',
                'message_human': '...',
                'message_tech': '...',
                'node_id': 'uuid',
                'severity': 'blocking' ou 'warning'
            }

    Returns:
        Lista de RecommendedAction
    """
    actions = []

    for issue in issues:
        code = issue.get('code')
        node_id = issue.get('node_id')

        if code in ACTION_MAPPINGS:
            mapping = ACTION_MAPPINGS[code]
            actions.append(RecommendedAction(
                action=mapping['action'],
                label=mapping['label'],
                description=mapping['description'],
                target_node_id=node_id,
                params={'issue_code': code}
            ))

    return actions


def get_action_for_error_code(error_code: str) -> Dict:
    """
    Retorna ação recomendada para um código de erro específico.

    Args:
        error_code: Código do erro

    Returns:
        Dict com action, label, description ou None
    """
    return ACTION_MAPPINGS.get(error_code)
