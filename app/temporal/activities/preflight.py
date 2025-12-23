"""
Preflight Activity - Valida tudo ANTES de executar workflow.

Feature 2: Preflight Real
"""
import asyncio
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from temporalio import activity

from app.models.workflow import Workflow
from app.models.execution import WorkflowExecution
from app.services.recommended_actions import get_recommended_actions, RecommendedAction


@dataclass
class PreflightIssue:
    """
    Issue encontrado durante preflight.

    Attributes:
        code: Código do erro (ex: 'drive.insufficient_permissions')
        domain: Domínio ('permissions', 'data', 'template', 'delivery')
        message_human: Mensagem para usuário
        message_tech: Mensagem técnica/debug
        node_id: UUID do node com problema
        severity: 'blocking' ou 'warning'
    """
    code: str
    domain: str
    message_human: str
    message_tech: str
    node_id: str
    severity: str  # 'blocking' ou 'warning'

    def to_dict(self):
        return {
            'code': self.code,
            'domain': self.domain,
            'message_human': self.message_human,
            'message_tech': self.message_tech,
            'node_id': self.node_id,
            'severity': self.severity
        }


@dataclass
class PreflightResult:
    """Resultado do preflight check"""
    blocking: List[PreflightIssue] = field(default_factory=list)
    warnings: List[PreflightIssue] = field(default_factory=list)
    recommended_actions: List[RecommendedAction] = field(default_factory=list)
    groups: Dict[str, List[PreflightIssue]] = field(default_factory=dict)

    @property
    def has_blocking_issues(self) -> bool:
        return len(self.blocking) > 0

    def to_dict(self):
        return {
            'blocking': [issue.to_dict() for issue in self.blocking],
            'warnings': [issue.to_dict() for issue in self.warnings],
            'recommended_actions': [action.to_dict() for action in self.recommended_actions],
            'groups': {k: [issue.to_dict() for issue in v] for k, v in self.groups.items()}
        }


async def run_preflight_check(workflow_id: str, trigger_data: dict) -> PreflightResult:
    """
    Executa preflight check (versão não-Temporal para uso direto).

    Validações:
    1. Dados - Campos required preenchidos, variáveis resolvem
    2. Template - Arquivo existe, tags válidas
    3. Permissões - Acesso ao template/pasta destino
    4. Entrega - Email válido, destino existe
    5. Assinatura - Conexão ativa, signers válidos

    Args:
        workflow_id: UUID do workflow
        trigger_data: Dados do trigger

    Returns:
        PreflightResult com issues encontrados
    """
    from app.database import db

    result = PreflightResult()

    # Buscar workflow
    workflow = db.session.get(Workflow, workflow_id)
    if not workflow:
        result.blocking.append(PreflightIssue(
            code='workflow_not_found',
            domain='workflow',
            message_human='Workflow não encontrado',
            message_tech=f'Workflow {workflow_id} not found in database',
            node_id='',
            severity='blocking'
        ))
        return result

    # Validar nodes
    for node in workflow.nodes:
        node_type = node.node_type
        parameters = node.parameters or {}

        # 1. Validação de dados
        await _validate_data(node, parameters, trigger_data, result)

        # 2. Validação de template (se for documento)
        if node_type in ['google-docs', 'google-slides', 'microsoft-word', 'microsoft-powerpoint']:
            await _validate_template(node, parameters, result)

        # 3. Validação de permissões (se usar Drive/OneDrive)
        if node_type in ['google-docs', 'google-slides', 'google-drive']:
            await _validate_permissions(node, parameters, result)

        # 4. Validação de entrega (se for email)
        if node_type in ['gmail', 'outlook']:
            await _validate_delivery(node, parameters, result)

        # 5. Validação de assinatura
        if node_type in ['clicksign', 'zapsign']:
            await _validate_signature(node, parameters, result)

    # Agrupar issues por domínio
    result.groups = _group_issues_by_domain(result.blocking + result.warnings)

    # Gerar ações recomendadas
    all_issues = [issue.to_dict() for issue in result.blocking + result.warnings]
    result.recommended_actions = get_recommended_actions(all_issues)

    return result


async def _validate_data(node, parameters: dict, trigger_data: dict, result: PreflightResult):
    """Valida campos required e variáveis"""
    # Verificar campos required vazios
    for key, value in parameters.items():
        if isinstance(value, str) and not value.strip():
            result.warnings.append(PreflightIssue(
                code='missing_required_field',
                domain='data',
                message_human=f'Campo "{key}" está vazio',
                message_tech=f'Required field "{key}" in node {node.id} is empty',
                node_id=str(node.id),
                severity='warning'
            ))

    # TODO: Validar se variáveis {{step.x.y}} resolvem (precisa contexto de execução)


async def _validate_template(node, parameters: dict, result: PreflightResult):
    """Valida template (arquivo existe, tags válidas)"""
    template_id = parameters.get('template_id') or parameters.get('templateId')

    if not template_id:
        result.blocking.append(PreflightIssue(
            code='template_not_selected',
            domain='template',
            message_human='Nenhum template selecionado',
            message_tech=f'No template_id found in node {node.id} parameters',
            node_id=str(node.id),
            severity='blocking'
        ))
        return

    # TODO: Verificar se template existe no Drive/OneDrive


async def _validate_permissions(node, parameters: dict, result: PreflightResult):
    """Valida permissões de acesso"""
    # TODO: Testar acesso real ao template e pasta destino
    # Por ora, apenas placeholder
    pass


async def _validate_delivery(node, parameters: dict, result: PreflightResult):
    """Valida entrega de email"""
    to_email = parameters.get('to')

    if not to_email:
        result.blocking.append(PreflightIssue(
            code='missing_recipient',
            domain='delivery',
            message_human='Destinatário não especificado',
            message_tech=f'No "to" field in node {node.id} parameters',
            node_id=str(node.id),
            severity='blocking'
        ))
        return

    # Validar formato de email básico
    if isinstance(to_email, str) and '@' not in to_email:
        result.blocking.append(PreflightIssue(
            code='invalid_email_format',
            domain='delivery',
            message_human=f'Email "{to_email}" é inválido',
            message_tech=f'Invalid email format: {to_email}',
            node_id=str(node.id),
            severity='blocking'
        ))


async def _validate_signature(node, parameters: dict, result: PreflightResult):
    """Valida configuração de assinatura"""
    signers = parameters.get('signers', [])

    if not signers:
        result.blocking.append(PreflightIssue(
            code='no_signers',
            domain='signature',
            message_human='Nenhum assinante configurado',
            message_tech=f'No signers in node {node.id} parameters',
            node_id=str(node.id),
            severity='blocking'
        ))
        return

    # Validar cada signer
    for signer in signers:
        if not signer.get('email'):
            result.warnings.append(PreflightIssue(
                code='signer_missing_email',
                domain='signature',
                message_human='Assinante sem email',
                message_tech=f'Signer in node {node.id} missing email field',
                node_id=str(node.id),
                severity='warning'
            ))


def _group_issues_by_domain(issues: List[PreflightIssue]) -> Dict[str, List[PreflightIssue]]:
    """Agrupa issues por domínio"""
    groups = {}

    for issue in issues:
        domain = issue.domain
        if domain not in groups:
            groups[domain] = []
        groups[domain].append(issue)

    return groups


# === Temporal Activity ===

@activity.defn(name='run_preflight')
async def run_preflight(execution_id: str) -> dict:
    """
    Temporal activity para executar preflight check.

    Args:
        execution_id: UUID da execução

    Returns:
        Dict com resultado do preflight
    """
    from app.database import db

    execution = db.session.get(WorkflowExecution, execution_id)

    if not execution:
        return {'error': 'Execution not found'}

    result = await run_preflight_check(
        workflow_id=str(execution.workflow_id),
        trigger_data=execution.trigger_data or {}
    )

    # Atualizar execution com resultado
    execution.update_preflight_summary(
        blocking_count=len(result.blocking),
        warning_count=len(result.warnings),
        groups={k: [issue.to_dict() for issue in v] for k, v in result.groups.items()}
    )

    if result.has_blocking_issues:
        execution.set_recommended_actions([action.to_dict() for action in result.recommended_actions])

    db.session.commit()

    return result.to_dict()
