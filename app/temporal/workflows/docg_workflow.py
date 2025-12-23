"""
DocGWorkflow - Workflow principal de execução do DocG.

Este workflow orquestra a execução de todos os nodes de um workflow,
incluindo pausas para aprovação e assinatura.
"""
import asyncio
from datetime import timedelta, datetime
from typing import Dict, Any, List, Optional
from temporalio import workflow
from temporalio.common import RetryPolicy

from ..config import get_config, SignalNames

# Importar activities com alias para uso no workflow
with workflow.unsafe.imports_passed_through():
    from ..activities import (
        load_execution,
        update_current_node,
        save_execution_context,
        pause_execution,
        resume_execution,
        complete_execution,
        fail_execution,
        add_execution_log,
        execute_trigger_node,
        execute_document_node,
        create_approval,
        expire_approval,
        create_signature_request,
        expire_signature,
        execute_email_node,
        execute_webhook_node,
    )


@workflow.defn(name="DocGWorkflow")
class DocGWorkflow:
    """
    Workflow principal do DocG.
    
    Processa nodes sequencialmente:
    1. Trigger: Extrai dados da fonte
    2. Documents: Gera documentos
    3. Approval: Pausa e aguarda aprovação humana
    4. Signature: Pausa e aguarda assinaturas
    5. Email: Envia notificações
    
    Signals:
    - approval_decision: Recebe decisão de aprovação
    - signature_update: Recebe update de assinatura
    """
    
    def __init__(self):
        # Estado de signals
        self._approval_decision: Optional[Dict[str, Any]] = None
        self._signature_status: Optional[Dict[str, Any]] = None

        # Novos signals (F10: Pause/Resume)
        self._resume_requested: bool = False
        self._resume_data: Optional[Dict[str, Any]] = None
        self._cancel_requested: bool = False
        self._cancel_reason: Optional[str] = None

        # Context acumulado
        self._source_data: Dict[str, Any] = {}
        self._source_object_id: str = ""
        self._source_object_type: str = ""
        self._generated_documents: List[Dict[str, Any]] = []
        self._signature_requests: List[Dict[str, Any]] = []
    
    @workflow.signal(name=SignalNames.APPROVAL_DECISION)
    async def approval_decision_signal(self, data: Dict[str, Any]):
        """
        Recebe signal de decisão de aprovação.
        
        Args:
            data: {approval_id, decision: 'approved'|'rejected'}
        """
        workflow.logger.info(f"Signal recebido: approval_decision = {data}")
        self._approval_decision = data
    
    @workflow.signal(name=SignalNames.SIGNATURE_UPDATE)
    async def signature_update_signal(self, data: Dict[str, Any]):
        """
        Recebe signal de update de assinatura.

        Args:
            data: {signature_request_id, status: 'signed'|'declined'|...}
        """
        workflow.logger.info(f"Signal recebido: signature_update = {data}")
        self._signature_status = data

    @workflow.signal(name='resume_after_review')
    async def resume_after_review_signal(self, data: Dict[str, Any]):
        """
        Recebe signal para retomar execução após needs_review (preflight fix).

        Feature 10: Pause/Resume via Signals

        Args:
            data: Dados adicionais para retomada (opcional)
        """
        workflow.logger.info(f"Signal recebido: resume_after_review = {data}")
        self._resume_requested = True
        self._resume_data = data

    @workflow.signal(name='cancel')
    async def cancel_signal(self, data: Dict[str, Any]):
        """
        Recebe signal para cancelar execução.

        Feature 10: Pause/Resume via Signals

        Args:
            data: {reason: str}
        """
        reason = data.get('reason', 'User requested')
        workflow.logger.info(f"Signal recebido: cancel - reason={reason}")
        self._cancel_requested = True
        self._cancel_reason = reason
    
    @workflow.run
    async def run(self, execution_id: str) -> Dict[str, Any]:
        """
        Executa o workflow.
        
        Args:
            execution_id: ID da WorkflowExecution
        
        Returns:
            {status: 'completed'|'failed', error: str|None}
        """
        config = get_config()
        
        try:
            # 1. Carregar execution e nodes
            workflow.logger.info(f"Iniciando workflow para execução {execution_id}")
            
            execution_data = await workflow.execute_activity(
                load_execution,
                execution_id,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=3)
            )
            
            nodes = execution_data['nodes']
            workflow_id = execution_data['workflow']['id']
            organization_id = execution_data['organization_id']
            trigger_data = execution_data['execution'].get('trigger_data', {})
            
            workflow.logger.info(f"Carregados {len(nodes)} nodes para workflow {workflow_id}")
            
            # 2. Processar nodes com suporte a branching
            # Separar trigger node dos action nodes
            trigger_node = nodes[0] if nodes and nodes[0].get('position') == 1 else None
            action_nodes = [n for n in nodes if n.get('position', 0) > 1]

            # Processar trigger primeiro
            if trigger_node:
                node_id = trigger_node['id']
                node_type = trigger_node['node_type']

                workflow.logger.info(f"Executando trigger: {node_type} ({node_id})")

                await workflow.execute_activity(
                    update_current_node,
                    {'execution_id': execution_id, 'node_id': node_id},
                    start_to_close_timeout=timedelta(seconds=10)
                )

                started_at = workflow.now()

                try:
                    await self._execute_trigger(
                        execution_id, trigger_node, workflow_id, organization_id, trigger_data, config
                    )

                    await workflow.execute_activity(
                        add_execution_log,
                        {
                            'execution_id': execution_id,
                            'node_id': node_id,
                            'node_type': node_type,
                            'status': 'success',
                            'started_at': started_at.isoformat(),
                            'completed_at': workflow.now().isoformat()
                        },
                        start_to_close_timeout=timedelta(seconds=10)
                    )
                except Exception as e:
                    await workflow.execute_activity(
                        add_execution_log,
                        {
                            'execution_id': execution_id,
                            'node_id': node_id,
                            'node_type': node_type,
                            'status': 'failed',
                            'started_at': started_at.isoformat(),
                            'completed_at': workflow.now().isoformat(),
                            'error': str(e)
                        },
                        start_to_close_timeout=timedelta(seconds=10)
                    )
                    raise

            # Processar action nodes com branching
            # Criar índice de nodes por ID para acesso rápido
            nodes_by_id = {n['id']: n for n in action_nodes}
            executed_steps = {}  # step_id -> output

            # Começar do primeiro action node
            current_node = action_nodes[0] if action_nodes else None

            while current_node:
                node_id = current_node['id']
                node_type = current_node['node_type']
                node_position = current_node['position']

                workflow.logger.info(f"Executando node {node_position}: {node_type} ({node_id})")

                # Atualizar current_node
                await workflow.execute_activity(
                    update_current_node,
                    {'execution_id': execution_id, 'node_id': node_id},
                    start_to_close_timeout=timedelta(seconds=10)
                )

                started_at = workflow.now()

                try:
                    # Executar baseado no tipo
                    if node_type in ['google-docs', 'google-slides', 'microsoft-word', 'microsoft-powerpoint', 'uploaded-document', 'file-upload']:
                        await self._execute_document(
                            execution_id, current_node, workflow_id, organization_id, config
                        )

                    elif node_type in ['review-documents', 'human-in-loop']:
                        await self._execute_approval(
                            execution_id, current_node, workflow_id, organization_id, config
                        )

                    elif node_type in ['request-signatures', 'signature', 'clicksign']:
                        await self._execute_signature(
                            execution_id, current_node, workflow_id, organization_id, config
                        )

                    elif node_type in ['gmail', 'outlook']:
                        await self._execute_email(
                            execution_id, current_node, workflow_id, organization_id, config
                        )

                    elif node_type == 'webhook':
                        await self._execute_webhook(
                            execution_id, current_node, workflow_id, organization_id, config
                        )

                    else:
                        workflow.logger.warning(f"Tipo de node não suportado: {node_type}")

                    # Log de sucesso
                    await workflow.execute_activity(
                        add_execution_log,
                        {
                            'execution_id': execution_id,
                            'node_id': node_id,
                            'node_type': node_type,
                            'status': 'success',
                            'started_at': started_at.isoformat(),
                            'completed_at': workflow.now().isoformat()
                        },
                        start_to_close_timeout=timedelta(seconds=10)
                    )

                    # Armazenar output para branching
                    executed_steps[node_id] = {
                        'node_type': node_type,
                        'position': node_position,
                        'status': 'success'
                    }

                except Exception as e:
                    # Log de erro
                    await workflow.execute_activity(
                        add_execution_log,
                        {
                            'execution_id': execution_id,
                            'node_id': node_id,
                            'node_type': node_type,
                            'status': 'failed',
                            'started_at': started_at.isoformat(),
                            'completed_at': workflow.now().isoformat(),
                            'error': str(e)
                        },
                        start_to_close_timeout=timedelta(seconds=10)
                    )
                    raise

                # Determinar próximo node (branching ou sequencial)
                current_node = self._get_next_node(
                    current_node=current_node,
                    action_nodes=action_nodes,
                    nodes_by_id=nodes_by_id,
                    executed_steps=executed_steps
                )
            
            # 3. Completar execução
            await workflow.execute_activity(
                complete_execution,
                execution_id,
                start_to_close_timeout=timedelta(seconds=10)
            )
            
            workflow.logger.info(f"Workflow {workflow_id} completado com sucesso")
            
            return {'status': 'completed', 'error': None}
        
        except Exception as e:
            workflow.logger.error(f"Erro no workflow: {e}")
            
            # Marcar como falho
            await workflow.execute_activity(
                fail_execution,
                {'execution_id': execution_id, 'error_message': str(e)},
                start_to_close_timeout=timedelta(seconds=10)
            )
            
            return {'status': 'failed', 'error': str(e)}
    
    async def _execute_trigger(
        self, execution_id: str, node: Dict, workflow_id: str, 
        organization_id: str, trigger_data: Dict, config
    ):
        """Executa node de trigger"""
        result = await workflow.execute_activity(
            execute_trigger_node,
            {
                'execution_id': execution_id,
                'node': node,
                'trigger_data': trigger_data,
                'workflow_id': workflow_id,
                'organization_id': organization_id
            },
            start_to_close_timeout=timedelta(seconds=config.trigger_timeout),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )
        
        # Atualizar context
        self._source_data = result.get('source_data', {})
        self._source_object_id = result.get('source_object_id', '')
        self._source_object_type = result.get('source_object_type', '')
        
        # Salvar context
        await self._save_context(execution_id)
    
    async def _execute_document(
        self, execution_id: str, node: Dict, workflow_id: str, 
        organization_id: str, config
    ):
        """Executa node de documento"""
        result = await workflow.execute_activity(
            execute_document_node,
            {
                'execution_id': execution_id,
                'node': node,
                'workflow_id': workflow_id,
                'organization_id': organization_id,
                'source_data': self._source_data,
                'source_object_id': self._source_object_id,
                'source_object_type': self._source_object_type
            },
            start_to_close_timeout=timedelta(seconds=config.document_timeout),
            retry_policy=RetryPolicy(
                maximum_attempts=config.max_activity_retries,
                initial_interval=timedelta(seconds=config.initial_retry_interval_seconds),
                maximum_interval=timedelta(seconds=config.max_retry_interval_seconds),
                backoff_coefficient=config.retry_backoff_coefficient
            )
        )
        
        # Adicionar documento ao context
        self._generated_documents.append({
            'node_id': node['id'],
            'document_id': result['document_id'],
            'file_id': result['file_id'],
            'file_url': result['file_url'],
            'pdf_file_id': result.get('pdf_file_id'),
            'pdf_url': result.get('pdf_url')
        })
        
        # Salvar context
        await self._save_context(execution_id)
    
    async def _execute_approval(
        self, execution_id: str, node: Dict, workflow_id: str, 
        organization_id: str, config
    ):
        """Executa node de aprovação com pausa"""
        # 1. Criar approval
        approval_data = await workflow.execute_activity(
            create_approval,
            {
                'execution_id': execution_id,
                'node': node,
                'workflow_id': workflow_id,
                'organization_id': organization_id,
                'generated_documents': self._generated_documents,
                'source_data': self._source_data,
                'source_object_id': self._source_object_id,
                'source_object_type': self._source_object_type
            },
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )
        
        # 2. Marcar como pausado
        await workflow.execute_activity(
            pause_execution,
            execution_id,
            start_to_close_timeout=timedelta(seconds=10)
        )
        
        # 3. Calcular timeout
        node_config = node.get('config', {})
        timeout_hours = node_config.get('timeout_hours', config.default_approval_timeout_hours)
        
        workflow.logger.info(f"Aguardando aprovação (timeout: {timeout_hours}h)")
        
        # 4. Esperar signal OU timeout
        self._approval_decision = None
        
        try:
            await workflow.wait_condition(
                lambda: self._approval_decision is not None,
                timeout=timedelta(hours=timeout_hours)
            )
        except asyncio.TimeoutError:
            # Expirou
            await workflow.execute_activity(
                expire_approval,
                approval_data['approval_id'],
                start_to_close_timeout=timedelta(seconds=10)
            )
            
            # Verificar se deve auto-aprovar
            if node_config.get('auto_approve_on_timeout', False):
                workflow.logger.info("Aprovação auto-aprovada por timeout")
            else:
                raise workflow.ApplicationError("Aprovação expirou")
        
        # 5. Verificar decisão
        if self._approval_decision:
            decision = self._approval_decision.get('decision')
            if decision == 'rejected':
                raise workflow.ApplicationError("Aprovação rejeitada")
            
            workflow.logger.info(f"Aprovação: {decision}")
        
        # 6. Retomar
        await workflow.execute_activity(
            resume_execution,
            execution_id,
            start_to_close_timeout=timedelta(seconds=10)
        )
    
    async def _execute_signature(
        self, execution_id: str, node: Dict, workflow_id: str, 
        organization_id: str, config
    ):
        """Executa node de assinatura com pausa"""
        # 1. Criar signature request
        sig_data = await workflow.execute_activity(
            create_signature_request,
            {
                'execution_id': execution_id,
                'node': node,
                'workflow_id': workflow_id,
                'organization_id': organization_id,
                'generated_documents': self._generated_documents,
                'source_data': self._source_data
            },
            start_to_close_timeout=timedelta(seconds=config.signature_timeout),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )
        
        # Adicionar ao context
        self._signature_requests.append({
            'node_id': node['id'],
            'signature_request_id': sig_data['signature_request_id'],
            'external_id': sig_data['external_id'],
            'external_url': sig_data['external_url']
        })
        
        # 2. Marcar como pausado
        await workflow.execute_activity(
            pause_execution,
            execution_id,
            start_to_close_timeout=timedelta(seconds=10)
        )
        
        # 3. Calcular timeout
        node_config = node.get('config', {})
        timeout_days = node_config.get('expiration_days', config.default_signature_timeout_days)
        
        workflow.logger.info(f"Aguardando assinatura (timeout: {timeout_days}d)")
        
        # 4. Esperar signal OU timeout
        self._signature_status = None
        
        try:
            await workflow.wait_condition(
                lambda: self._signature_status is not None,
                timeout=timedelta(days=timeout_days)
            )
        except asyncio.TimeoutError:
            # Expirou
            await workflow.execute_activity(
                expire_signature,
                sig_data['signature_request_id'],
                start_to_close_timeout=timedelta(seconds=10)
            )
            raise workflow.ApplicationError("Assinatura expirou")
        
        # 5. Verificar status
        if self._signature_status:
            status = self._signature_status.get('status')
            if status == 'declined':
                raise workflow.ApplicationError("Assinatura recusada")
            elif status != 'signed':
                raise workflow.ApplicationError(f"Status de assinatura inválido: {status}")
            
            workflow.logger.info("Documento assinado com sucesso")
        
        # 6. Retomar
        await workflow.execute_activity(
            resume_execution,
            execution_id,
            start_to_close_timeout=timedelta(seconds=10)
        )
    
    async def _execute_email(
        self, execution_id: str, node: Dict, workflow_id: str, 
        organization_id: str, config
    ):
        """Executa node de email"""
        await workflow.execute_activity(
            execute_email_node,
            {
                'execution_id': execution_id,
                'node': node,
                'workflow_id': workflow_id,
                'organization_id': organization_id,
                'source_data': self._source_data,
                'generated_documents': self._generated_documents
            },
            start_to_close_timeout=timedelta(seconds=config.email_timeout),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )
    
    async def _execute_webhook(
        self, execution_id: str, node: Dict, workflow_id: str, 
        organization_id: str, config
    ):
        """Executa node de webhook (envia POST com resultado da execução)"""
        # Construir execution_context com dados acumulados
        execution_context = {
            'workflow_id': workflow_id,
            'execution_id': execution_id,
            'source_data': self._source_data,
            'source_object_id': self._source_object_id,
            'source_object_type': self._source_object_type,
            'generated_documents': self._generated_documents,
            'signature_requests': self._signature_requests,
            'metadata': {}
        }
        
        # Executar webhook
        webhook_timeout = getattr(config, 'webhook_timeout', 30)
        await workflow.execute_activity(
            execute_webhook_node,
            {
                'execution_id': execution_id,
                'node': node,
                'execution_context': execution_context
            },
            start_to_close_timeout=timedelta(seconds=webhook_timeout),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )
    
    async def _save_context(self, execution_id: str):
        """Salva snapshot do context atual"""
        context = {
            'source_data': self._source_data,
            'source_object_id': self._source_object_id,
            'source_object_type': self._source_object_type,
            'generated_documents': self._generated_documents,
            'signature_requests': self._signature_requests
        }

        await workflow.execute_activity(
            save_execution_context,
            {'execution_id': execution_id, 'context': context},
            start_to_close_timeout=timedelta(seconds=10)
        )

    def _get_next_node(
        self,
        current_node: Dict[str, Any],
        action_nodes: List[Dict[str, Any]],
        nodes_by_id: Dict[str, Dict[str, Any]],
        executed_steps: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Determina o próximo node considerando branching.

        Args:
            current_node: Node atual
            action_nodes: Lista de todos action nodes
            nodes_by_id: Índice de nodes por ID
            executed_steps: Steps já executados

        Returns:
            Próximo node ou None se terminou
        """
        structural_type = current_node.get('structural_type', 'single')

        # Se é um branch node, avaliar condições
        if structural_type == 'branch':
            branch_conditions = current_node.get('branch_conditions', [])

            for branch in branch_conditions:
                conditions = branch.get('conditions')
                next_node_id = branch.get('next_node_id')

                # Default path (conditions == None)
                if conditions is None:
                    if next_node_id and next_node_id in nodes_by_id:
                        return nodes_by_id[next_node_id]
                    continue

                # Avaliar condições
                if self._evaluate_branch_conditions(conditions, executed_steps):
                    if next_node_id and next_node_id in nodes_by_id:
                        return nodes_by_id[next_node_id]

        # Fallback: próximo sequencial por position
        current_position = current_node.get('position', 0)
        for node in action_nodes:
            if node.get('position') == current_position + 1:
                return node

        return None

    def _evaluate_branch_conditions(
        self,
        conditions: Dict[str, Any],
        executed_steps: Dict[str, Any]
    ) -> bool:
        """
        Avalia condições de branching.

        Args:
            conditions: Estrutura de condições
            executed_steps: Steps executados com seus outputs

        Returns:
            True se condições são satisfeitas
        """
        rules = conditions.get('rules', [])
        condition_type = conditions.get('type', 'and')

        if not rules:
            return True

        results = []
        for rule in rules:
            field = rule.get('field', '')
            operator = rule.get('operator', '==')
            expected = rule.get('value')

            # Extrair valor do campo
            actual = self._get_field_value(field, executed_steps)

            # Comparar
            result = self._compare_values(actual, operator, expected)
            results.append(result)

        if condition_type == 'and':
            return all(results)
        return any(results)

    def _get_field_value(self, field: str, executed_steps: Dict[str, Any]) -> Any:
        """Extrai valor de um campo do contexto"""
        # Se tem referência {{step.xxx.yyy}}
        if '{{' in field and '}}' in field:
            # Extrair path
            match = field.replace('{{', '').replace('}}', '').strip()
            parts = match.split('.')

            if parts[0] == 'step' and len(parts) >= 3:
                step_id = parts[1]
                if step_id in executed_steps:
                    return self._get_nested(executed_steps[step_id], parts[2:])
            elif parts[0] == 'trigger':
                return self._get_nested(self._source_data, parts[1:])

        return field

    def _get_nested(self, obj: Any, keys: List[str]) -> Any:
        """Obtém valor aninhado de um objeto"""
        for key in keys:
            if isinstance(obj, dict):
                obj = obj.get(key)
            elif isinstance(obj, list):
                try:
                    obj = obj[int(key)]
                except (ValueError, IndexError):
                    return None
            else:
                return None
            if obj is None:
                return None
        return obj

    def _compare_values(self, actual: Any, operator: str, expected: Any) -> bool:
        """Compara valores com operador"""
        try:
            if operator == '==':
                return str(actual) == str(expected)
            elif operator == '!=':
                return str(actual) != str(expected)
            elif operator == '>':
                return float(actual) > float(expected)
            elif operator == '<':
                return float(actual) < float(expected)
            elif operator == '>=':
                return float(actual) >= float(expected)
            elif operator == '<=':
                return float(actual) <= float(expected)
            elif operator == 'contains':
                return str(expected) in str(actual)
            elif operator == 'not_contains':
                return str(expected) not in str(actual)
            elif operator == 'starts_with':
                return str(actual).startswith(str(expected))
            elif operator == 'ends_with':
                return str(actual).endswith(str(expected))
            elif operator == 'is_empty':
                return not actual or actual == '' or actual == []
            elif operator == 'is_not_empty':
                return bool(actual) and actual != '' and actual != []
            else:
                return False
        except (ValueError, TypeError):
            return False

