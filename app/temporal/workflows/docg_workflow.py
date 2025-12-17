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
            
            # 2. Processar cada node sequencialmente
            for node in nodes:
                node_id = node['id']
                node_type = node['node_type']
                node_position = node['position']
                
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
                    if node_type in ['hubspot', 'webhook', 'google-forms', 'trigger']:
                        await self._execute_trigger(
                            execution_id, node, workflow_id, organization_id, trigger_data, config
                        )
                    
                    elif node_type in ['google-docs', 'google-slides', 'microsoft-word', 'microsoft-powerpoint']:
                        await self._execute_document(
                            execution_id, node, workflow_id, organization_id, config
                        )
                    
                    elif node_type in ['review-documents', 'human-in-loop']:
                        await self._execute_approval(
                            execution_id, node, workflow_id, organization_id, config
                        )
                    
                    elif node_type in ['request-signatures', 'signature', 'clicksign']:
                        await self._execute_signature(
                            execution_id, node, workflow_id, organization_id, config
                        )
                    
                    elif node_type in ['gmail', 'outlook']:
                        await self._execute_email(
                            execution_id, node, workflow_id, organization_id, config
                        )
                    
                    elif node_type == 'webhook':
                        await self._execute_webhook(
                            execution_id, node, workflow_id, organization_id, config
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

