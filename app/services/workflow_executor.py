"""
WorkflowExecutor - Orquestrador de execução de workflows com nodes.
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging
import time

from app.database import db
from app.models import Workflow, WorkflowNode, WorkflowExecution, GeneratedDocument
from app.services.data_sources.hubspot import HubSpotDataSource

logger = logging.getLogger(__name__)


class ExecutionContext:
    """Contexto de execução passado entre nodes"""
    
    def __init__(self, workflow_id: str, execution_id: str, source_object_id: str, source_object_type: str):
        self.workflow_id = workflow_id
        self.execution_id = execution_id
        self.source_object_id = source_object_id
        self.source_object_type = source_object_type
        self.source_data: Dict[str, Any] = {}
        self.generated_documents: List[Dict[str, Any]] = []
        self.signature_requests: List[Dict[str, Any]] = []
        self.metadata: Dict[str, Any] = {
            'started_at': datetime.utcnow(),
            'current_node_position': 0,
            'errors': []
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte context para dicionário"""
        return {
            'workflow_id': self.workflow_id,
            'execution_id': self.execution_id,
            'source_object_id': self.source_object_id,
            'source_object_type': self.source_object_type,
            'source_data': self.source_data,
            'generated_documents': self.generated_documents,
            'signature_requests': self.signature_requests,
            'metadata': {
                **self.metadata,
                'started_at': self.metadata['started_at'].isoformat() if isinstance(self.metadata['started_at'], datetime) else self.metadata['started_at']
            }
        }
    
    def add_error(self, node_id: str, node_type: str, error: str):
        """Adiciona erro ao context"""
        self.metadata['errors'].append({
            'node_id': node_id,
            'node_type': node_type,
            'error': error
        })


class NodeExecutor:
    """Classe base para executores de nodes"""
    
    def execute(self, node: WorkflowNode, context: ExecutionContext) -> ExecutionContext:
        """
        Executa o node e atualiza o context.
        
        Args:
            node: Node a ser executado
            context: Contexto de execução
        
        Returns:
            Context atualizado
        """
        raise NotImplementedError("Subclasses devem implementar execute()")


class TriggerNodeExecutor(NodeExecutor):
    """Executor para trigger nodes"""
    
    def execute(self, node: WorkflowNode, context: ExecutionContext) -> ExecutionContext:
        """Extrai dados do HubSpot baseado na configuração do trigger"""
        config = node.config or {}
        source_connection_id = config.get('source_connection_id')
        source_object_type = config.get('source_object_type') or context.source_object_type
        
        if not source_connection_id:
            raise ValueError('source_connection_id não configurado no trigger node')
        
        # Buscar conexão
        from app.models import DataSourceConnection
        connection = DataSourceConnection.query.get(source_connection_id)
        if not connection:
            raise ValueError(f'Conexão não encontrada: {source_connection_id}')
        
        if connection.source_type != 'hubspot':
            raise ValueError(f'Tipo de conexão não suportado: {connection.source_type}')
        
        # Extrair dados do HubSpot
        data_source = HubSpotDataSource(connection)
        source_data = data_source.get_object_data(
            source_object_type,
            context.source_object_id
        )
        
        # Normalizar dados (mover properties para nível raiz)
        if isinstance(source_data, dict) and 'properties' in source_data:
            properties = source_data.pop('properties', {})
            if isinstance(properties, dict):
                source_data.update(properties)
        
        context.source_data = source_data
        context.metadata['current_node_position'] = node.position
        
        logger.info(f"Trigger node executado: extraídos dados de {source_object_type} {context.source_object_id}")
        
        return context


class GoogleDocsNodeExecutor(NodeExecutor):
    """Executor para Google Docs nodes"""
    
    def execute(self, node: WorkflowNode, context: ExecutionContext) -> ExecutionContext:
        """Gera documento no Google Docs"""
        from app.services.document_generation.generator import DocumentGenerator
        from app.routes.google_drive_routes import get_google_credentials
        from app.models import Template, WorkflowFieldMapping, AIGenerationMapping
        import uuid
        
        config = node.config or {}
        template_id = config.get('template_id')
        
        if not template_id:
            raise ValueError('template_id não configurado no Google Docs node')
        
        # Buscar template
        template = Template.query.get(template_id)
        if not template:
            raise ValueError(f'Template não encontrado: {template_id}')
        
        # Buscar workflow para obter organization_id
        workflow = Workflow.query.get(context.workflow_id)
        if not workflow:
            raise ValueError(f'Workflow não encontrado: {context.workflow_id}')
        
        # Obter credenciais do Google
        google_creds = get_google_credentials(workflow.organization_id)
        if not google_creds:
            raise ValueError('Credenciais do Google não configuradas')
        
        # Criar generator
        generator = DocumentGenerator(google_creds)
        
        # Buscar field mappings do node (se configurado no config)
        field_mappings_data = config.get('field_mappings', [])
        mappings = {}
        for mapping_data in field_mappings_data:
            template_tag = mapping_data.get('template_tag')
            source_field = mapping_data.get('source_field')
            if template_tag and source_field:
                mappings[template_tag] = source_field
        
        # Gerar nome do documento
        from app.services.document_generation.tag_processor import TagProcessor
        from datetime import datetime
        
        output_name_template = config.get('output_name_template', '{{object_type}} - {{timestamp}}')
        
        # Adicionar campos especiais para o template de nome
        data_with_meta = {
            **context.source_data,
            'date': datetime.utcnow().strftime('%Y-%m-%d'),
            'timestamp': datetime.utcnow().strftime('%Y%m%d_%H%M%S'),
            'object_type': context.source_object_type
        }
        
        doc_name = TagProcessor.replace_tags(output_name_template, data_with_meta)
        
        # Copiar template
        new_doc = generator.google_docs.copy_template(
            template_id=template.google_file_id,
            new_name=doc_name,
            folder_id=config.get('output_folder_id')
        )
        
        # Processar AI mappings (se houver, associados ao workflow por enquanto)
        # TODO: Associar AI mappings ao node no futuro
        ai_replacements = {}
        ai_mappings = list(workflow.ai_mappings)
        if ai_mappings:
            # Criar métricas para rastreamento
            from app.services.document_generation.generator import AIGenerationMetrics
            ai_metrics = AIGenerationMetrics()
            ai_replacements = generator._process_ai_tags(
                workflow=workflow,
                source_data=context.source_data,
                metrics=ai_metrics
            )
        
        # Combinar dados
        combined_data = {**context.source_data, **ai_replacements}
        
        # Substituir tags
        generator.google_docs.replace_tags_in_document(
            document_id=new_doc['id'],
            data=combined_data,
            mappings=mappings
        )
        
        # Gerar PDF se configurado
        pdf_result = None
        if config.get('create_pdf', True):
            pdf_bytes = generator.google_docs.export_as_pdf(new_doc['id'])
            pdf_result = generator._upload_pdf(
                pdf_bytes,
                f"{doc_name}.pdf",
                config.get('output_folder_id')
            )
        
        # Criar registro do documento
        generated_doc = GeneratedDocument(
            organization_id=workflow.organization_id,
            workflow_id=workflow.id,
            source_connection_id=workflow.source_connection_id,
            source_object_type=context.source_object_type,
            source_object_id=context.source_object_id,
            template_id=template.id,
            template_version=template.version,
            name=doc_name,
            google_doc_id=new_doc['id'],
            google_doc_url=new_doc['url'],
            status='generated',
            generated_data=context.source_data,
            generated_at=datetime.utcnow()
        )
        
        if pdf_result:
            generated_doc.pdf_file_id = pdf_result['id']
            generated_doc.pdf_url = pdf_result['url']
        
        db.session.add(generated_doc)
        db.session.commit()
        
        # Adicionar ao context
        context.generated_documents.append({
            'node_id': str(node.id),
            'document_id': str(generated_doc.id),
            'google_doc_id': new_doc['id'],
            'google_doc_url': new_doc['url'],
            'pdf_file_id': pdf_result['id'] if pdf_result else None,
            'pdf_url': pdf_result['url'] if pdf_result else None
        })
        
        context.metadata['current_node_position'] = node.position
        
        logger.info(f"Google Docs node executado: documento {generated_doc.id} gerado")
        
        return context


class ClicksignNodeExecutor(NodeExecutor):
    """Executor para Clicksign nodes"""
    
    def execute(self, node: WorkflowNode, context: ExecutionContext) -> ExecutionContext:
        """Envia documento para assinatura no Clicksign"""
        config = node.config or {}
        connection_id = config.get('connection_id')
        recipients = config.get('recipients', [])
        document_source = config.get('document_source', 'previous_node')
        
        if not connection_id:
            raise ValueError('connection_id não configurado no Clicksign node')
        
        if not recipients:
            raise ValueError('recipients não configurado no Clicksign node')
        
        # Buscar documento
        document = None
        if document_source == 'previous_node' and context.generated_documents:
            # Usar último documento gerado
            last_doc = context.generated_documents[-1]
            document_id = last_doc.get('document_id')
            if document_id:
                document = GeneratedDocument.query.get(document_id)
        elif document_source == 'specific_document_id':
            document_id = config.get('document_id')
            if document_id:
                document = GeneratedDocument.query.get(document_id)
        
        if not document:
            raise ValueError('Documento não encontrado para envio de assinatura')
        
        if not document.pdf_file_id:
            raise ValueError('Documento não possui PDF gerado')
        
        # Buscar conexão Clicksign
        from app.models import DataSourceConnection
        connection = DataSourceConnection.query.get(connection_id)
        if not connection or connection.source_type != 'clicksign':
            raise ValueError(f'Conexão Clicksign não encontrada: {connection_id}')
        
        # TODO: Implementar integração com Clicksign
        # Por enquanto, apenas registrar no context
        context.signature_requests.append({
            'node_id': str(node.id),
            'document_id': str(document.id),
            'connection_id': str(connection_id),
            'recipients': recipients,
            'status': 'pending'
        })
        
        context.metadata['current_node_position'] = node.position
        
        logger.info(f"Clicksign node executado: documento {document.id} preparado para assinatura")
        
        return context


class WebhookNodeExecutor(NodeExecutor):
    """Executor para Webhook nodes"""
    
    def execute(self, node: WorkflowNode, context: ExecutionContext) -> ExecutionContext:
        """Chama webhook com dados do context"""
        import requests
        
        config = node.config or {}
        url = config.get('url')
        method = config.get('method', 'POST').upper()
        headers = config.get('headers', {})
        body_template = config.get('body_template', '{}')
        
        if not url:
            raise ValueError('url não configurado no Webhook node')
        
        # Preparar body (substituir placeholders se necessário)
        # Por enquanto, enviar context completo
        body = {
            'workflow_id': context.workflow_id,
            'execution_id': context.execution_id,
            'source_object_id': context.source_object_id,
            'source_object_type': context.source_object_type,
            'source_data': context.source_data,
            'generated_documents': context.generated_documents,
            'signature_requests': context.signature_requests
        }
        
        # Chamar webhook
        try:
            response = requests.request(
                method=method,
                url=url,
                json=body,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            
            logger.info(f"Webhook node executado: {url} retornou {response.status_code}")
        except Exception as e:
            logger.error(f"Erro ao chamar webhook {url}: {str(e)}")
            raise
        
        context.metadata['current_node_position'] = node.position
        
        return context


class WorkflowExecutor:
    """Orquestrador principal de execução de workflows"""
    
    def __init__(self):
        self.executors = {
            'trigger': TriggerNodeExecutor(),
            'google-docs': GoogleDocsNodeExecutor(),
            'clicksign': ClicksignNodeExecutor(),
            'webhook': WebhookNodeExecutor()
        }
    
    def execute_workflow(
        self,
        workflow: Workflow,
        source_object_id: str,
        source_object_type: str,
        user_id: Optional[str] = None
    ) -> WorkflowExecution:
        """
        Executa um workflow processando nodes sequencialmente.
        
        Args:
            workflow: Workflow com nodes configurados
            source_object_id: ID do objeto na fonte (HubSpot)
            source_object_type: Tipo do objeto (deal, contact, etc)
            user_id: ID do usuário que está executando
        
        Returns:
            WorkflowExecution com resultado da execução
        """
        # Criar registro de execução
        execution = WorkflowExecution(
            workflow_id=workflow.id,
            trigger_type='manual',
            trigger_data={
                'source_object_id': source_object_id,
                'source_object_type': source_object_type
            },
            status='running'
        )
        db.session.add(execution)
        db.session.commit()
        
        start_time = datetime.utcnow()
        
        try:
            # Buscar nodes ordenados por position
            nodes = WorkflowNode.query.filter_by(
                workflow_id=workflow.id
            ).order_by(WorkflowNode.position).all()
            
            if not nodes:
                raise ValueError('Workflow não possui nodes configurados')
            
            # Criar execution context
            context = ExecutionContext(
                workflow_id=str(workflow.id),
                execution_id=str(execution.id),
                source_object_id=source_object_id,
                source_object_type=source_object_type
            )
            
            # Processar cada node sequencialmente
            for node in nodes:
                try:
                    executor = self.executors.get(node.node_type)
                    if not executor:
                        raise ValueError(f'Executor não encontrado para node_type: {node.node_type}')
                    
                    context = executor.execute(node, context)
                    
                except Exception as e:
                    # Registrar erro mas continuar (ou parar, dependendo da configuração)
                    context.add_error(str(node.id), node.node_type, str(e))
                    logger.error(f"Erro ao executar node {node.id} ({node.node_type}): {str(e)}")
                    # Para erros críticos, interromper execução
                    if node.node_type in ['trigger', 'google-docs']:
                        raise
            
            # Atualizar execução com resultado
            end_time = datetime.utcnow()
            execution.status = 'completed' if not context.metadata['errors'] else 'failed'
            execution.completed_at = end_time
            execution.execution_time_ms = int((end_time - start_time).total_seconds() * 1000)
            
            # Associar documento gerado se houver
            if context.generated_documents:
                last_doc_id = context.generated_documents[-1].get('document_id')
                if last_doc_id:
                    execution.generated_document_id = last_doc_id
            
            db.session.commit()
            
            logger.info(f"Workflow {workflow.id} executado com sucesso em {execution.execution_time_ms}ms")
            
            return execution
            
        except Exception as e:
            logger.error(f"Erro ao executar workflow {workflow.id}: {str(e)}")
            
            execution.status = 'failed'
            execution.error_message = str(e)
            execution.completed_at = datetime.utcnow()
            execution.execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            db.session.commit()
            
            raise
