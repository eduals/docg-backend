"""
WorkflowExecutor - Orquestrador de execução de workflows com nodes.
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging
import time
import requests

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
        """Extrai dados baseado na configuração do trigger"""
        config = node.config or {}
        
        # Determinar tipo de trigger baseado no node_type
        if node.node_type == 'webhook':
            trigger_type = 'webhook'
        elif node.node_type == 'google-forms':
            trigger_type = 'google-forms'
        elif node.node_type == 'hubspot':
            trigger_type = 'hubspot'
        elif node.node_type == 'trigger':
            # Compatibilidade: usar config.trigger_type
            trigger_type = config.get('trigger_type', 'hubspot')
        else:
            # Fallback
            trigger_type = 'hubspot'
        
        if trigger_type == 'webhook':
            # Para webhook trigger, os dados já vêm no context.source_data
            # Apenas validar que existem
            if not context.source_data:
                raise ValueError('source_data não encontrado no context (webhook trigger)')
            context.metadata['current_node_position'] = node.position
            logger.info(f"Webhook trigger node executado: dados recebidos do webhook")
            return context
        
        elif trigger_type == 'google-forms':
            # TODO: Implementar lógica para Google Forms
            raise NotImplementedError('Google Forms trigger ainda não implementado')
        
        else:
            # Trigger HubSpot (comportamento original)
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
            
            logger.info(f"HubSpot trigger node executado: extraídos dados de {source_object_type} {context.source_object_id}")
            
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


class MicrosoftWordNodeExecutor(NodeExecutor):
    """Executor para Microsoft Word nodes"""
    
    def execute(self, node: WorkflowNode, context: ExecutionContext) -> ExecutionContext:
        """Gera documento no Microsoft Word"""
        from app.services.document_generation.microsoft_word import MicrosoftWordService
        from app.models import Template, GeneratedDocument, DataSourceConnection
        from datetime import datetime
        from app.services.document_generation.tag_processor import TagProcessor
        
        config = node.config or {}
        template_id = config.get('template_id')
        connection_id = config.get('connection_id')
        
        if not template_id:
            raise ValueError('template_id não configurado no Microsoft Word node')
        
        if not connection_id:
            raise ValueError('connection_id não configurado no Microsoft Word node')
        
        # Buscar template
        template = Template.query.get(template_id)
        if not template:
            raise ValueError(f'Template não encontrado: {template_id}')
        
        # Buscar workflow para obter organization_id
        workflow = Workflow.query.get(context.workflow_id)
        if not workflow:
            raise ValueError(f'Workflow não encontrado: {context.workflow_id}')
        
        # Buscar conexão Microsoft
        connection = DataSourceConnection.query.filter_by(
            id=connection_id,
            organization_id=workflow.organization_id,
            source_type='microsoft'
        ).first()
        
        if not connection:
            raise ValueError(f'Conexão Microsoft não encontrada: {connection_id}')
        
        # Obter access token
        credentials = connection.get_decrypted_credentials()
        access_token = credentials.get('access_token')
        
        if not access_token:
            raise ValueError('Access token não encontrado na conexão Microsoft')
        
        # Verificar se token expirou e renovar se necessário
        expires_at_str = credentials.get('expires_at')
        if expires_at_str:
            expires_at = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
            if expires_at < datetime.utcnow():
                # Renovar token
                from app.routes.microsoft_oauth_routes import _refresh_microsoft_token
                if not _refresh_microsoft_token(connection):
                    raise ValueError('Não foi possível renovar token Microsoft')
                credentials = connection.get_decrypted_credentials()
                access_token = credentials.get('access_token')
        
        # Criar serviço
        word_service = MicrosoftWordService({
            'access_token': access_token,
            'refresh_token': credentials.get('refresh_token'),
            'expires_at': credentials.get('expires_at'),
            'user_email': credentials.get('user_email'),
        })
        
        # Buscar field mappings do node
        field_mappings_data = config.get('field_mappings', [])
        mappings = {}
        for mapping_data in field_mappings_data:
            template_tag = mapping_data.get('template_tag')
            source_field = mapping_data.get('source_field')
            if template_tag and source_field:
                mappings[template_tag] = source_field
        
        # Gerar nome do documento
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
        new_doc = word_service.copy_template(
            template_id=template.microsoft_file_id or template.google_file_id,  # Fallback para google_file_id
            new_name=doc_name,
            folder_id=config.get('output_folder_id')
        )
        
        # Processar AI mappings (se houver)
        ai_replacements = {}
        ai_mappings = list(workflow.ai_mappings)
        if ai_mappings:
            try:
                from app.services.document_generation.generator import DocumentGenerator, AIGenerationMetrics
                from app.routes.google_oauth_routes import get_google_credentials
                
                # Usar credenciais Google para gerar conteúdo AI (mesmo sistema)
                google_creds = get_google_credentials(workflow.organization_id)
                if google_creds:
                    ai_metrics = AIGenerationMetrics()
                    generator = DocumentGenerator(google_creds)
                    ai_replacements = generator._process_ai_tags(
                        workflow=workflow,
                        source_data=context.source_data,
                        metrics=ai_metrics
                    )
                    logger.info(f'AI tags processadas para Word: {len(ai_replacements)} substituições')
                else:
                    logger.warning('Credenciais Google não encontradas para processar AI tags')
            except Exception as e:
                logger.exception(f'Erro ao processar AI tags para Word: {str(e)}')
                # Continuar sem AI tags se houver erro
        
        # Combinar dados
        combined_data = {**context.source_data, **ai_replacements}
        
        # Substituir tags
        word_service.replace_tags_in_document(
            document_id=new_doc['id'],
            data=combined_data,
            mappings=mappings
        )
        
        # Gerar PDF se configurado
        pdf_result = None
        if config.get('create_pdf', True):
            try:
                pdf_bytes = word_service.export_as_pdf(new_doc['id'])
                # Upload PDF para OneDrive
                pdf_name = f"{doc_name}.pdf"
                pdf_upload_response = requests.put(
                    f'https://graph.microsoft.com/v1.0/me/drive/items/{config.get("output_folder_id", "root")}/children/{pdf_name}/content',
                    headers={'Authorization': f'Bearer {access_token}'},
                    data=pdf_bytes
                )
                if pdf_upload_response.ok:
                    pdf_file = pdf_upload_response.json()
                    pdf_result = {
                        'id': pdf_file['id'],
                        'url': pdf_file.get('webUrl')
                    }
            except Exception as e:
                logger.warning(f'Erro ao gerar PDF do Word: {str(e)}')
        
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
            google_doc_id=new_doc['id'],  # Reutilizar campo para Microsoft file ID
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
            'microsoft_file_id': new_doc['id'],
            'microsoft_file_url': new_doc['url'],
            'pdf_file_id': pdf_result['id'] if pdf_result else None,
            'pdf_url': pdf_result['url'] if pdf_result else None
        })
        
        context.metadata['current_node_position'] = node.position
        
        logger.info(f"Microsoft Word node executado: documento {generated_doc.id} gerado")
        
        return context


class GoogleSlidesNodeExecutor(NodeExecutor):
    """Executor para Google Slides nodes"""
    
    def execute(self, node: WorkflowNode, context: ExecutionContext) -> ExecutionContext:
        """Gera apresentação no Google Slides"""
        from app.services.document_generation.generator import DocumentGenerator
        from app.services.document_generation.google_slides import GoogleSlidesService
        from app.routes.google_drive_routes import get_google_credentials
        from app.models import Template, GeneratedDocument
        from datetime import datetime
        from app.services.document_generation.tag_processor import TagProcessor
        
        config = node.config or {}
        template_id = config.get('template_id')
        
        if not template_id:
            raise ValueError('template_id não configurado no Google Slides node')
        
        # Buscar template
        template = Template.query.get(template_id)
        if not template:
            raise ValueError(f'Template não encontrado: {template_id}')
        
        # Buscar workflow
        workflow = Workflow.query.get(context.workflow_id)
        if not workflow:
            raise ValueError(f'Workflow não encontrado: {context.workflow_id}')
        
        # Obter credenciais do Google
        google_creds = get_google_credentials(workflow.organization_id)
        if not google_creds:
            raise ValueError('Credenciais do Google não configuradas')
        
        # Criar serviço
        slides_service = GoogleSlidesService(google_creds)
        
        # Buscar field mappings
        field_mappings_data = config.get('field_mappings', [])
        mappings = {}
        for mapping_data in field_mappings_data:
            template_tag = mapping_data.get('template_tag')
            source_field = mapping_data.get('source_field')
            if template_tag and source_field:
                mappings[template_tag] = source_field
        
        # Gerar nome da apresentação
        output_name_template = config.get('output_name_template', '{{object_type}} - {{timestamp}}')
        
        data_with_meta = {
            **context.source_data,
            'date': datetime.utcnow().strftime('%Y-%m-%d'),
            'timestamp': datetime.utcnow().strftime('%Y%m%d_%H%M%S'),
            'object_type': context.source_object_type
        }
        
        pres_name = TagProcessor.replace_tags(output_name_template, data_with_meta)
        
        # Copiar template
        new_pres = slides_service.copy_template(
            template_id=template.google_file_id,
            new_name=pres_name,
            folder_id=config.get('output_folder_id')
        )
        
        # Processar AI mappings
        ai_replacements = {}
        ai_mappings = list(workflow.ai_mappings)
        if ai_mappings:
            from app.services.document_generation.generator import AIGenerationMetrics
            ai_metrics = AIGenerationMetrics()
            generator = DocumentGenerator(google_creds)
            ai_replacements = generator._process_ai_tags(
                workflow=workflow,
                source_data=context.source_data,
                metrics=ai_metrics
            )
        
        # Combinar dados
        combined_data = {**context.source_data, **ai_replacements}
        
        # Substituir tags
        slides_service.replace_tags_in_presentation(
            presentation_id=new_pres['id'],
            data=combined_data,
            mappings=mappings
        )
        
        # Gerar PDF se configurado
        pdf_result = None
        if config.get('create_pdf', True):
            pdf_bytes = slides_service.export_as_pdf(new_pres['id'])
            # Upload PDF para Google Drive
            from app.services.document_generation.generator import DocumentGenerator
            generator = DocumentGenerator(google_creds)
            pdf_result = generator._upload_pdf(
                pdf_bytes,
                f"{pres_name}.pdf",
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
            name=pres_name,
            google_doc_id=new_pres['id'],
            google_doc_url=new_pres['url'],
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
            'google_slides_id': new_pres['id'],
            'google_slides_url': new_pres['url'],
            'pdf_file_id': pdf_result['id'] if pdf_result else None,
            'pdf_url': pdf_result['url'] if pdf_result else None
        })
        
        context.metadata['current_node_position'] = node.position
        
        logger.info(f"Google Slides node executado: apresentação {generated_doc.id} gerada")
        
        return context


class MicrosoftPowerPointNodeExecutor(NodeExecutor):
    """Executor para Microsoft PowerPoint nodes"""
    
    def execute(self, node: WorkflowNode, context: ExecutionContext) -> ExecutionContext:
        """Gera apresentação no Microsoft PowerPoint"""
        from app.services.document_generation.microsoft_powerpoint import MicrosoftPowerPointService
        from app.models import Template, GeneratedDocument, DataSourceConnection
        from datetime import datetime
        from app.services.document_generation.tag_processor import TagProcessor
        
        config = node.config or {}
        template_id = config.get('template_id')
        connection_id = config.get('connection_id')
        
        if not template_id:
            raise ValueError('template_id não configurado no Microsoft PowerPoint node')
        
        if not connection_id:
            raise ValueError('connection_id não configurado no Microsoft PowerPoint node')
        
        # Buscar template
        template = Template.query.get(template_id)
        if not template:
            raise ValueError(f'Template não encontrado: {template_id}')
        
        # Buscar workflow
        workflow = Workflow.query.get(context.workflow_id)
        if not workflow:
            raise ValueError(f'Workflow não encontrado: {context.workflow_id}')
        
        # Buscar conexão Microsoft
        connection = DataSourceConnection.query.filter_by(
            id=connection_id,
            organization_id=workflow.organization_id,
            source_type='microsoft'
        ).first()
        
        if not connection:
            raise ValueError(f'Conexão Microsoft não encontrada: {connection_id}')
        
        # Obter access token
        credentials = connection.get_decrypted_credentials()
        access_token = credentials.get('access_token')
        
        if not access_token:
            raise ValueError('Access token não encontrado na conexão Microsoft')
        
        # Verificar se token expirou e renovar se necessário
        expires_at_str = credentials.get('expires_at')
        if expires_at_str:
            expires_at = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
            if expires_at < datetime.utcnow():
                from app.routes.microsoft_oauth_routes import _refresh_microsoft_token
                if not _refresh_microsoft_token(connection):
                    raise ValueError('Não foi possível renovar token Microsoft')
                credentials = connection.get_decrypted_credentials()
                access_token = credentials.get('access_token')
        
        # Criar serviço
        ppt_service = MicrosoftPowerPointService({
            'access_token': access_token,
            'refresh_token': credentials.get('refresh_token'),
            'expires_at': credentials.get('expires_at'),
            'user_email': credentials.get('user_email'),
        })
        
        # Buscar field mappings
        field_mappings_data = config.get('field_mappings', [])
        mappings = {}
        for mapping_data in field_mappings_data:
            template_tag = mapping_data.get('template_tag')
            source_field = mapping_data.get('source_field')
            if template_tag and source_field:
                mappings[template_tag] = source_field
        
        # Gerar nome da apresentação
        output_name_template = config.get('output_name_template', '{{object_type}} - {{timestamp}}')
        
        data_with_meta = {
            **context.source_data,
            'date': datetime.utcnow().strftime('%Y-%m-%d'),
            'timestamp': datetime.utcnow().strftime('%Y%m%d_%H%M%S'),
            'object_type': context.source_object_type
        }
        
        pres_name = TagProcessor.replace_tags(output_name_template, data_with_meta)
        
        # Copiar template
        new_pres = ppt_service.copy_template(
            template_id=template.microsoft_file_id or template.google_file_id,
            new_name=pres_name,
            folder_id=config.get('output_folder_id')
        )
        
        # Processar AI mappings (se houver)
        ai_replacements = {}
        ai_mappings = list(workflow.ai_mappings)
        if ai_mappings:
            try:
                from app.services.document_generation.generator import DocumentGenerator, AIGenerationMetrics
                from app.routes.google_oauth_routes import get_google_credentials
                
                # Usar credenciais Google para gerar conteúdo AI (mesmo sistema)
                google_creds = get_google_credentials(workflow.organization_id)
                if google_creds:
                    ai_metrics = AIGenerationMetrics()
                    generator = DocumentGenerator(google_creds)
                    ai_replacements = generator._process_ai_tags(
                        workflow=workflow,
                        source_data=context.source_data,
                        metrics=ai_metrics
                    )
                    logger.info(f'AI tags processadas para PowerPoint: {len(ai_replacements)} substituições')
                else:
                    logger.warning('Credenciais Google não encontradas para processar AI tags')
            except Exception as e:
                logger.exception(f'Erro ao processar AI tags para PowerPoint: {str(e)}')
                # Continuar sem AI tags se houver erro
        
        # Combinar dados
        combined_data = {**context.source_data, **ai_replacements}
        
        # Substituir tags
        ppt_service.replace_tags_in_presentation(
            presentation_id=new_pres['id'],
            data=combined_data,
            mappings=mappings
        )
        
        # Gerar PDF se configurado
        pdf_result = None
        if config.get('create_pdf', True):
            try:
                pdf_bytes = ppt_service.export_as_pdf(new_pres['id'])
                pdf_name = f"{pres_name}.pdf"
                pdf_upload_response = requests.put(
                    f'https://graph.microsoft.com/v1.0/me/drive/items/{config.get("output_folder_id", "root")}/children/{pdf_name}/content',
                    headers={'Authorization': f'Bearer {access_token}'},
                    data=pdf_bytes
                )
                if pdf_upload_response.ok:
                    pdf_file = pdf_upload_response.json()
                    pdf_result = {
                        'id': pdf_file['id'],
                        'url': pdf_file.get('webUrl')
                    }
            except Exception as e:
                logger.warning(f'Erro ao gerar PDF do PowerPoint: {str(e)}')
        
        # Criar registro do documento
        generated_doc = GeneratedDocument(
            organization_id=workflow.organization_id,
            workflow_id=workflow.id,
            source_connection_id=workflow.source_connection_id,
            source_object_type=context.source_object_type,
            source_object_id=context.source_object_id,
            template_id=template.id,
            template_version=template.version,
            name=pres_name,
            google_doc_id=new_pres['id'],  # Reutilizar campo
            google_doc_url=new_pres['url'],
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
            'microsoft_file_id': new_pres['id'],
            'microsoft_file_url': new_pres['url'],
            'pdf_file_id': pdf_result['id'] if pdf_result else None,
            'pdf_url': pdf_result['url'] if pdf_result else None
        })
        
        context.metadata['current_node_position'] = node.position
        
        logger.info(f"Microsoft PowerPoint node executado: apresentação {generated_doc.id} gerada")
        
        return context


class GmailEmailNodeExecutor(NodeExecutor):
    """Executor para Gmail email nodes"""
    
    def execute(self, node: WorkflowNode, context: ExecutionContext) -> ExecutionContext:
        """Envia email via Gmail SMTP"""
        from app.services.email_service import EmailService
        from app.models import DataSourceConnection, GeneratedDocument
        from app.services.document_generation.tag_processor import TagProcessor
        
        config = node.config or {}
        connection_id = config.get('connection_id')
        
        if not connection_id:
            raise ValueError('connection_id não configurado no Gmail email node')
        
        # Buscar workflow
        workflow = Workflow.query.get(context.workflow_id)
        if not workflow:
            raise ValueError(f'Workflow não encontrado: {context.workflow_id}')
        
        # Buscar conexão Gmail SMTP
        connection = DataSourceConnection.query.filter_by(
            id=connection_id,
            organization_id=workflow.organization_id,
            source_type='gmail_smtp'
        ).first()
        
        if not connection:
            raise ValueError(f'Conexão Gmail SMTP não encontrada: {connection_id}')
        
        # Obter credenciais
        credentials = connection.get_decrypted_credentials()
        smtp_host = credentials.get('smtp_host', 'smtp.gmail.com')
        smtp_port = credentials.get('smtp_port', 587)
        username = credentials.get('username')
        password = credentials.get('password')
        use_tls = credentials.get('use_tls', True)
        
        if not username or not password:
            raise ValueError('Credenciais SMTP incompletas')
        
        # Processar templates de email
        to_emails = config.get('to', [])
        subject_template = config.get('subject_template', '')
        body_template = config.get('body_template', '')
        body_type = config.get('body_type', 'html')
        
        # Substituir tags
        data = context.source_data
        to_processed = [TagProcessor.replace_tags(email, data) for email in to_emails]
        subject = TagProcessor.replace_tags(subject_template, data)
        body = TagProcessor.replace_tags(body_template, data)
        
        # Processar anexos se configurado
        attachments = []
        if config.get('attach_documents', False):
            document_node_ids = config.get('document_node_ids', [])
            for doc_info in context.generated_documents:
                if str(doc_info.get('node_id')) in document_node_ids:
                    # Buscar documento gerado
                    doc = GeneratedDocument.query.get(doc_info.get('document_id'))
                    if doc:
                        try:
                            pdf_bytes = None
                            filename = doc.name or f'document_{doc.id}.pdf'
                            
                            # Tentar baixar PDF do Google Drive
                            if doc.pdf_file_id:
                                from app.services.document_generation.google_docs import GoogleDocsService
                                from app.services.document_generation.google_slides import GoogleSlidesService
                                from app.routes.google_drive_routes import get_google_credentials
                                
                                google_creds = get_google_credentials(workflow.organization_id)
                                if google_creds:
                                    # Verificar tipo de arquivo pelo template
                                    template = doc.template
                                    if template:
                                        if template.google_file_type == 'document' or not template.google_file_type:
                                            docs_service = GoogleDocsService(google_creds)
                                            pdf_bytes = docs_service.export_as_pdf(doc.pdf_file_id)
                                        elif template.google_file_type == 'presentation':
                                            slides_service = GoogleSlidesService(google_creds)
                                            pdf_bytes = slides_service.export_as_pdf(doc.pdf_file_id)
                                    else:
                                        # Fallback: assumir documento
                                        docs_service = GoogleDocsService(google_creds)
                                        pdf_bytes = docs_service.export_as_pdf(doc.pdf_file_id)
                            
                            # Se não encontrou PDF do Google, tentar Microsoft via template
                            if not pdf_bytes and doc.template:
                                template = doc.template
                                if template.microsoft_file_id:
                                    from app.services.document_generation.microsoft_word import MicrosoftWordService
                                    from app.services.document_generation.microsoft_powerpoint import MicrosoftPowerPointService
                                    from app.routes.microsoft_oauth_routes import get_microsoft_credentials
                                    
                                    microsoft_creds = get_microsoft_credentials(workflow.organization_id)
                                    if microsoft_creds:
                                        # Verificar tipo de arquivo pelo template
                                        if template.microsoft_file_type == 'word' or template.microsoft_file_type == 'document':
                                            word_service = MicrosoftWordService(microsoft_creds)
                                            pdf_bytes = word_service.export_as_pdf(template.microsoft_file_id)
                                        elif template.microsoft_file_type == 'powerpoint' or template.microsoft_file_type == 'presentation':
                                            ppt_service = MicrosoftPowerPointService(microsoft_creds)
                                            pdf_bytes = ppt_service.export_as_pdf(template.microsoft_file_id)
                            
                            if pdf_bytes:
                                attachments.append({
                                    'filename': filename,
                                    'content': pdf_bytes,
                                    'content_type': 'application/pdf'
                                })
                                logger.info(f'PDF anexado: {filename}')
                            else:
                                logger.warning(f'Não foi possível baixar PDF para documento {doc.id}')
                        except Exception as e:
                            logger.exception(f'Erro ao baixar PDF para anexo: {str(e)}')
                            # Continuar mesmo se falhar
        
        # Enviar email
        EmailService.send_via_smtp(
            smtp_host=smtp_host,
            smtp_port=smtp_port,
            username=username,
            password=password,
            use_tls=use_tls,
            to=to_processed,
            subject=subject,
            body=body,
            body_type=body_type,
            cc=config.get('cc', []),
            bcc=config.get('bcc', []),
            attachments=attachments if attachments else None
        )
        
        context.metadata['current_node_position'] = node.position
        logger.info(f"Gmail email node executado: email enviado para {to_processed}")
        
        return context


class OutlookEmailNodeExecutor(NodeExecutor):
    """Executor para Outlook email nodes"""
    
    def execute(self, node: WorkflowNode, context: ExecutionContext) -> ExecutionContext:
        """Envia email via Outlook (Microsoft Graph API)"""
        from app.services.email_service import EmailService
        from app.models import DataSourceConnection, GeneratedDocument
        from app.services.document_generation.tag_processor import TagProcessor
        from datetime import datetime
        
        config = node.config or {}
        connection_id = config.get('connection_id')
        
        if not connection_id:
            raise ValueError('connection_id não configurado no Outlook email node')
        
        # Buscar workflow
        workflow = Workflow.query.get(context.workflow_id)
        if not workflow:
            raise ValueError(f'Workflow não encontrado: {context.workflow_id}')
        
        # Buscar conexão Microsoft
        connection = DataSourceConnection.query.filter_by(
            id=connection_id,
            organization_id=workflow.organization_id,
            source_type='microsoft'
        ).first()
        
        if not connection:
            raise ValueError(f'Conexão Microsoft não encontrada: {connection_id}')
        
        # Obter access token
        credentials = connection.get_decrypted_credentials()
        access_token = credentials.get('access_token')
        from_email = credentials.get('user_email')
        
        if not access_token or not from_email:
            raise ValueError('Access token ou email não encontrado na conexão Microsoft')
        
        # Verificar se token expirou e renovar se necessário
        expires_at_str = credentials.get('expires_at')
        if expires_at_str:
            expires_at = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
            if expires_at < datetime.utcnow():
                from app.routes.microsoft_oauth_routes import _refresh_microsoft_token
                if not _refresh_microsoft_token(connection):
                    raise ValueError('Não foi possível renovar token Microsoft')
                credentials = connection.get_decrypted_credentials()
                access_token = credentials.get('access_token')
        
        # Processar templates de email
        to_emails = config.get('to', [])
        subject_template = config.get('subject_template', '')
        body_template = config.get('body_template', '')
        body_type = config.get('body_type', 'html')
        
        # Substituir tags
        data = context.source_data
        to_processed = [TagProcessor.replace_tags(email, data) for email in to_emails]
        subject = TagProcessor.replace_tags(subject_template, data)
        body = TagProcessor.replace_tags(body_template, data)
        
        # Processar anexos se configurado
        attachments = []
        if config.get('attach_documents', False):
            document_node_ids = config.get('document_node_ids', [])
            for doc_info in context.generated_documents:
                if str(doc_info.get('node_id')) in document_node_ids:
                    # Buscar documento gerado
                    doc = GeneratedDocument.query.get(doc_info.get('document_id'))
                    if doc:
                        try:
                            pdf_bytes = None
                            filename = doc.name or f'document_{doc.id}.pdf'
                            
                            # Tentar baixar PDF do Microsoft OneDrive via template
                            if not pdf_bytes and doc.template:
                                template = doc.template
                                if template.microsoft_file_id:
                                    from app.services.document_generation.microsoft_word import MicrosoftWordService
                                    from app.services.document_generation.microsoft_powerpoint import MicrosoftPowerPointService
                                    from app.routes.microsoft_oauth_routes import get_microsoft_credentials
                                    
                                    microsoft_creds = get_microsoft_credentials(workflow.organization_id)
                                    if microsoft_creds:
                                        # Verificar tipo de arquivo pelo template
                                        if template.microsoft_file_type == 'word' or template.microsoft_file_type == 'document':
                                            word_service = MicrosoftWordService(microsoft_creds)
                                            pdf_bytes = word_service.export_as_pdf(template.microsoft_file_id)
                                        elif template.microsoft_file_type == 'powerpoint' or template.microsoft_file_type == 'presentation':
                                            ppt_service = MicrosoftPowerPointService(microsoft_creds)
                                            pdf_bytes = ppt_service.export_as_pdf(template.microsoft_file_id)
                            
                            # Se não encontrou PDF do Microsoft, tentar Google
                            if not pdf_bytes and doc.pdf_file_id:
                                from app.services.document_generation.google_docs import GoogleDocsService
                                from app.services.document_generation.google_slides import GoogleSlidesService
                                from app.routes.google_drive_routes import get_google_credentials
                                
                                google_creds = get_google_credentials(workflow.organization_id)
                                if google_creds:
                                    # Verificar tipo de arquivo pelo template
                                    template = doc.template
                                    if template:
                                        if template.google_file_type == 'document' or not template.google_file_type:
                                            docs_service = GoogleDocsService(google_creds)
                                            pdf_bytes = docs_service.export_as_pdf(doc.pdf_file_id)
                                        elif template.google_file_type == 'presentation':
                                            slides_service = GoogleSlidesService(google_creds)
                                            pdf_bytes = slides_service.export_as_pdf(doc.pdf_file_id)
                                    else:
                                        # Fallback: assumir documento
                                        docs_service = GoogleDocsService(google_creds)
                                        pdf_bytes = docs_service.export_as_pdf(doc.pdf_file_id)
                            
                            if pdf_bytes:
                                attachments.append({
                                    'filename': filename,
                                    'content': pdf_bytes,
                                    'content_type': 'application/pdf'
                                })
                                logger.info(f'PDF anexado: {filename}')
                            else:
                                logger.warning(f'Não foi possível baixar PDF para documento {doc.id}')
                        except Exception as e:
                            logger.exception(f'Erro ao baixar PDF para anexo: {str(e)}')
                            # Continuar mesmo se falhar
        
        # Enviar email
        EmailService.send_via_graph_api(
            access_token=access_token,
            from_email=from_email,
            to=to_processed,
            subject=subject,
            body=body,
            body_type=body_type,
            cc=config.get('cc', []),
            bcc=config.get('bcc', []),
            attachments=attachments if attachments else None
        )
        
        context.metadata['current_node_position'] = node.position
        logger.info(f"Outlook email node executado: email enviado para {to_processed}")
        
        return context


class HumanInLoopNodeExecutor(NodeExecutor):
    """Executor para Human-in-the-Loop nodes (aprovação)"""
    
    def execute(self, node: WorkflowNode, context: ExecutionContext) -> ExecutionContext:
        """Pausa execução e cria aprovação"""
        from app.models import WorkflowApproval, WorkflowExecution
        from datetime import datetime, timedelta
        import secrets
        
        config = node.config or {}
        approver_emails = config.get('approver_emails', [])
        message_template = config.get('message_template', 'Por favor, revise os documentos gerados e aprove ou rejeite.')
        timeout_hours = config.get('timeout_hours', 48)
        auto_approve_on_timeout = config.get('auto_approve_on_timeout', False)
        
        if not approver_emails:
            raise ValueError('approver_emails não configurado no Human-in-Loop node')
        
        # Buscar execução atual
        execution = WorkflowExecution.query.filter_by(
            workflow_id=context.workflow_id,
            status='running'
        ).order_by(WorkflowExecution.created_at.desc()).first()
        
        if not execution:
            raise ValueError('Execução não encontrada')
        
        # Coletar URLs dos documentos gerados
        document_urls = []
        for doc_info in context.generated_documents:
            if doc_info.get('pdf_url'):
                document_urls.append({
                    'name': doc_info.get('name', 'Documento'),
                    'url': doc_info.get('pdf_url')
                })
            elif doc_info.get('google_doc_url'):
                document_urls.append({
                    'name': doc_info.get('name', 'Documento'),
                    'url': doc_info.get('google_doc_url')
                })
            elif doc_info.get('microsoft_file_url'):
                document_urls.append({
                    'name': doc_info.get('name', 'Documento'),
                    'url': doc_info.get('microsoft_file_url')
                })
        
        # Criar aprovação para cada aprovador
        approvals = []
        for approver_email in approver_emails:
            approval = WorkflowApproval(
                workflow_execution_id=execution.id,
                workflow_id=context.workflow_id,
                node_id=node.id,
                execution_context={
                    'source_object_id': context.source_object_id,
                    'source_object_type': context.source_object_type,
                    'source_data': context.source_data,
                    'metadata': context.metadata,
                    'generated_documents': context.generated_documents
                },
                approver_email=approver_email,
                approval_token=secrets.token_urlsafe(32),
                status='pending',
                message_template=message_template,
                timeout_hours=timeout_hours,
                auto_approve_on_timeout=auto_approve_on_timeout,
                document_urls=document_urls,
                expires_at=datetime.utcnow() + timedelta(hours=timeout_hours)
            )
            db.session.add(approval)
            approvals.append(approval)
        
        # Marcar execução como pausada
        execution.status = 'paused'
        db.session.commit()
        
        # Enviar emails de aprovação
        try:
            from app.services.email_service import EmailService
            from app.services.document_generation.tag_processor import TagProcessor
            import os
            
            # Obter URL base do frontend
            frontend_url = os.getenv('FRONTEND_URL', os.getenv('APP_URL', 'https://app.exemplo.com'))
            
            for approval in approvals:
                approval_url = f"{frontend_url.rstrip('/')}/approve/{approval.approval_token}"
                
                # Processar mensagem template
                processed_message = TagProcessor.replace_tags(message_template, context.source_data)
                
                # Construir HTML do email
                documents_html = ''
                if document_urls:
                    documents_html = '<ul>'
                    for doc in document_urls:
                        documents_html += f'<li><a href="{doc.get("url", "#")}">{doc.get("name", "Documento")}</a></li>'
                    documents_html += '</ul>'
                
                email_body = f"""
                <html>
                <body>
                    <p>{processed_message}</p>
                    {documents_html}
                    <p>
                        <a href="{approval_url}" style="display: inline-block; padding: 10px 20px; background-color: #2563eb; color: white; text-decoration: none; border-radius: 5px; margin-right: 10px;">Aprovar</a>
                        <a href="{approval_url}" style="display: inline-block; padding: 10px 20px; background-color: #dc2626; color: white; text-decoration: none; border-radius: 5px;">Rejeitar</a>
                    </p>
                    <p style="margin-top: 20px; font-size: 12px; color: #666;">
                        Este link expira em {timeout_hours} horas.
                    </p>
                </body>
                </html>
                """
                
                # Tentar enviar via conexão de email configurada na organização
                # Por enquanto, apenas log (requer configuração de email da organização)
                logger.info(f'Link de aprovação para {approval.approver_email}: {approval_url}')
                logger.info(f'Email de aprovação preparado para {approval.approver_email}')
                
                # TODO: Implementar envio real quando sistema de email da organização estiver configurado
                # Por enquanto, o link pode ser copiado do log ou aprovado diretamente pela URL
                
        except Exception as e:
            logger.exception(f'Erro ao preparar emails de aprovação: {str(e)}')
            # Não falhar a execução se email falhar, apenas log
        
        # Não continuar para próximo node (execução pausada)
        # A execução será retomada quando a aprovação for aprovada/rejeitada
        context.metadata['current_node_position'] = node.position
        context.metadata['paused'] = True
        context.metadata['approval_ids'] = [str(a.id) for a in approvals]
        
        logger.info(f"Human-in-Loop node executado: execução pausada, {len(approvals)} aprovações criadas")
        
        return context


class SignatureNodeExecutor(NodeExecutor):
    """Executor genérico para nodes de assinatura"""
    
    def execute(self, node: WorkflowNode, context: ExecutionContext) -> ExecutionContext:
        """Executa node de assinatura usando adapter do provider"""
        config = node.config or {}
        provider = config.get('provider', 'clicksign')  # Default para compatibilidade
        connection_id = config.get('connection_id')
        recipients = config.get('recipients', [])
        message = config.get('message')
        document_source = config.get('document_source', 'previous_node')
        
        # Validações
        if not connection_id:
            raise ValueError('connection_id não configurado no node de assinatura')
        
        if not recipients:
            raise ValueError('recipients não configurado no node de assinatura')
        
        # Buscar documento
        document = self._get_document(context, config, document_source)
        if not document:
            raise ValueError('Documento não encontrado para envio de assinatura')
        
        # Obter adapter via factory
        from app.services.integrations.signature.factory import SignatureProviderFactory
        from app.models import Workflow
        
        # Buscar workflow para obter organization_id
        workflow = Workflow.query.get(context.workflow_id)
        if not workflow:
            raise ValueError(f'Workflow não encontrado: {context.workflow_id}')
        
        adapter = SignatureProviderFactory.get_adapter(
            provider=provider,
            connection_id=connection_id,
            organization_id=str(workflow.organization_id)
        )
        
        # Enviar para assinatura
        signature_request = adapter.send_document_for_signature(
            document=document,
            signers=recipients,
            message=message
        )
        
        # Adicionar ao context
        context.signature_requests.append({
            'signature_request_id': str(signature_request.id),
            'provider': provider,
            'external_id': signature_request.external_id,
            'external_url': signature_request.external_url
        })
        
        context.metadata['current_node_position'] = node.position
        
        logger.info(
            f"Signature node executado: documento {document.id} enviado para assinatura "
            f"via {provider} (envelope: {signature_request.external_id})"
        )
        
        return context
    
    def _get_document(
        self,
        context: ExecutionContext,
        config: dict,
        document_source: str
    ) -> Optional[GeneratedDocument]:
        """
        Busca documento baseado na configuração do node.
        
        Opções de document_source:
        - 'previous_node': Usa o último documento gerado no workflow
        - 'specific_node': Usa documento de um node específico (document_node_id)
        - 'specific_document': Usa um documento específico por ID (document_id)
        """
        if document_source == 'previous_node':
            # Usar último documento gerado que tenha PDF
            if context.generated_documents:
                # Buscar do último para o primeiro, pegando o primeiro que tenha PDF
                for doc_info in reversed(context.generated_documents):
                    document_id = doc_info.get('document_id')
                    pdf_file_id = doc_info.get('pdf_file_id')
                    
                    if document_id and pdf_file_id:
                        document = GeneratedDocument.query.get(document_id)
                        if document and document.pdf_file_id:
                            return document
                
                # Se nenhum tem PDF, pegar o último mesmo (pode exportar depois)
                last_doc = context.generated_documents[-1]
                document_id = last_doc.get('document_id')
                if document_id:
                    return GeneratedDocument.query.get(document_id)
        
        elif document_source == 'specific_node':
            # Buscar documento de node específico
            node_id = config.get('document_node_id')
            if node_id:
                # Buscar no context pelo node_id
                for doc_info in context.generated_documents:
                    if doc_info.get('node_id') == node_id:
                        document_id = doc_info.get('document_id')
                        if document_id:
                            return GeneratedDocument.query.get(document_id)
        
        elif document_source == 'specific_document':
            # Usar documento específico por ID
            document_id = config.get('document_id')
            if document_id:
                return GeneratedDocument.query.get(document_id)
        
        return None


# Manter ClicksignNodeExecutor para compatibilidade (delega para SignatureNodeExecutor)
class ClicksignNodeExecutor(SignatureNodeExecutor):
    """Executor para Clicksign nodes (compatibilidade - delega para SignatureNodeExecutor)"""
    pass


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
            # Triggers padronizados
            'hubspot': TriggerNodeExecutor(),        # NOVO: nome padronizado
            'webhook': TriggerNodeExecutor(),        # Trigger webhook
            'google-forms': TriggerNodeExecutor(),    # NOVO: nome padronizado
            # Documentos
            'google-docs': GoogleDocsNodeExecutor(),
            'google-slides': GoogleSlidesNodeExecutor(),
            'microsoft-word': MicrosoftWordNodeExecutor(),
            'microsoft-powerpoint': MicrosoftPowerPointNodeExecutor(),
            # Email
            'gmail': GmailEmailNodeExecutor(),
            'outlook': OutlookEmailNodeExecutor(),
            # Human in the Loop
            'review-documents': HumanInLoopNodeExecutor(),  # NOVO: nome padronizado
            'request-signatures': SignatureNodeExecutor(),   # NOVO: nome padronizado
            # Utilities
            # NOTA: 'webhook' como node externo será tratado depois - por enquanto apenas trigger webhook
            # Compatibilidade com nomes antigos (DEPRECATED)
            'trigger': TriggerNodeExecutor(),           # DEPRECATED
            'human-in-loop': HumanInLoopNodeExecutor(), # DEPRECATED
            'signature': SignatureNodeExecutor(),      # DEPRECATED
            'clicksign': ClicksignNodeExecutor(),       # DEPRECATED
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
                    if node.node_type in ['hubspot', 'webhook', 'google-forms', 'trigger', 'google-docs']:
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
