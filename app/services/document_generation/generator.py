from typing import Dict, Any, Optional, List
from datetime import datetime
import logging
import time

from app.database import db
from app.models import (
    Workflow, GeneratedDocument, Template,
    Organization, WorkflowExecution
)
from app.utils.encryption import decrypt_credentials
from .google_docs import GoogleDocsService
from .tag_processor import TagProcessor

logger = logging.getLogger(__name__)
ai_logger = logging.getLogger('docugen.ai')

class AIGenerationMetrics:
    """Classe para rastrear métricas de geração de IA"""
    
    def __init__(self):
        self.details: List[Dict] = []
        self.total_time_ms = 0
        self.total_tokens = 0
        self.total_cost = 0.0
        self.successful = 0
        self.failed = 0
    
    def add_success(self, mapping: Any, time_ms: float, tokens: int = 0, cost: float = 0.0):
        """Add successful AI generation metrics. mapping can be dict or object with ai_tag, provider, model attributes."""
        ai_tag = mapping.ai_tag if hasattr(mapping, 'ai_tag') else mapping.get('ai_tag', 'unknown')
        provider = mapping.provider if hasattr(mapping, 'provider') else mapping.get('provider', 'unknown')
        model = mapping.model if hasattr(mapping, 'model') else mapping.get('model', 'unknown')

        self.details.append({
            'tag': ai_tag,
            'provider': provider,
            'model': model,
            'time_ms': round(time_ms),
            'tokens': tokens,
            'cost_usd': cost,
            'status': 'success'
        })
        self.total_time_ms += time_ms
        self.total_tokens += tokens
        self.total_cost += cost
        self.successful += 1

    def add_failure(self, mapping: Any, error: str, time_ms: float = 0):
        """Add failed AI generation metrics. mapping can be dict or object with ai_tag, provider, model attributes."""
        ai_tag = mapping.ai_tag if hasattr(mapping, 'ai_tag') else mapping.get('ai_tag', 'unknown')
        provider = mapping.provider if hasattr(mapping, 'provider') else mapping.get('provider', 'unknown')
        model = mapping.model if hasattr(mapping, 'model') else mapping.get('model', 'unknown')

        self.details.append({
            'tag': ai_tag,
            'provider': provider,
            'model': model,
            'time_ms': round(time_ms),
            'status': 'failed',
            'error': error
        })
        self.total_time_ms += time_ms
        self.failed += 1
    
    def to_dict(self) -> Dict:
        return {
            'total_tags': len(self.details),
            'successful': self.successful,
            'failed': self.failed,
            'total_time_ms': round(self.total_time_ms),
            'total_tokens': self.total_tokens,
            'estimated_cost_usd': round(self.total_cost, 6),
            'details': self.details
        }


class DocumentGenerator:
    """
    Orquestrador principal de geração de documentos.
    Coordena a busca de dados, processamento de template e geração do documento.
    Suporta geração de texto via IA para tags {{ai:...}}.
    """
    
    def __init__(self, google_credentials):
        self.google_docs = GoogleDocsService(google_credentials)
        self._llm_service = None
    
    @property
    def llm_service(self):
        """Lazy load do serviço de LLM"""
        if self._llm_service is None:
            from app.services.ai import LLMService
            self._llm_service = LLMService()
        return self._llm_service
    
    def generate_from_workflow(
        self,
        workflow: Workflow,
        source_data: Dict[str, Any],
        source_object_id: str,
        user_id: str = None,
        organization_id: Any = None
    ) -> GeneratedDocument:
        """
        Gera um documento a partir de um workflow configurado.
        
        Args:
            workflow: Workflow com configurações
            source_data: Dados da fonte (já buscados)
            source_object_id: ID do objeto na fonte
            user_id: ID do usuário que está gerando
            organization_id: ID da organização (opcional, usa workflow.organization_id se não fornecido)
        
        Returns:
            GeneratedDocument criado
        """
        execution = None
        
        try:
            # Criar registro de execução
            execution = WorkflowExecution(
                workflow_id=workflow.id,
                trigger_type='manual',
                trigger_data={'source_object_id': source_object_id},
                status='running'
            )
            db.session.add(execution)
            db.session.commit()
            
            start_time = datetime.utcnow()
            
            # Verificar quota da organização
            org = workflow.organization
            if not org.can_generate_document():
                raise Exception('Limite de documentos atingido para este período')
            
            # Buscar template
            template = workflow.template
            if not template:
                raise Exception('Template não configurado no workflow')
            
            # Normalizar dados do HubSpot (move properties para nível raiz)
            source_data = self._normalize_hubspot_data(source_data)
            
            # Buscar mapeamentos de campos
            mappings = {
                m.template_tag: m.source_field 
                for m in workflow.field_mappings
            }
            
            # Processar tags AI antes de copiar o template
            ai_metrics = AIGenerationMetrics()
            ai_replacements = {}
            
            # Buscar tags AI do template (precisamos do conteúdo primeiro)
            # Por enquanto, vamos processar após copiar o template
            # O ideal seria ter cache do conteúdo do template
            
            # Gerar nome do documento
            doc_name = self._generate_document_name(
                workflow.output_name_template,
                source_data,
                workflow.source_object_type
            )
            
            # Copiar template
            new_doc = self.google_docs.copy_template(
                template_id=template.google_file_id,
                new_name=doc_name,
                folder_id=workflow.output_folder_id
            )
            
            # Processar tags AI primeiro
            ai_replacements = self._process_ai_tags(
                workflow=workflow,
                source_data=source_data,
                metrics=ai_metrics
            )
            
            # Combinar mapeamentos normais com substituições AI
            combined_data = {**source_data, **ai_replacements}
            
            # Substituir tags (normais e AI)
            self.google_docs.replace_tags_in_document(
                document_id=new_doc['id'],
                data=combined_data,
                mappings=mappings
            )
            
            # Usar organization_id fornecido ou do workflow
            # Isso garante consistência com o g.organization_id usado na query
            doc_org_id = organization_id if organization_id is not None else workflow.organization_id
            
            # Criar registro do documento gerado
            generated_doc = GeneratedDocument(
                organization_id=doc_org_id,
                workflow_id=workflow.id,
                source_connection_id=workflow.source_connection_id,
                source_object_type=workflow.source_object_type,
                source_object_id=source_object_id,
                template_id=template.id,
                template_version=template.version,
                name=doc_name,
                google_doc_id=new_doc['id'],
                google_doc_url=new_doc['url'],
                status='generated',
                generated_data=source_data,
                generated_by=user_id,
                generated_at=datetime.utcnow()
            )
            
            # Gerar PDF se configurado
            pdf_bytes = None
            if workflow.create_pdf:
                pdf_bytes = self.google_docs.export_as_pdf(new_doc['id'])
                pdf_result = self._upload_pdf(
                    pdf_bytes, 
                    f"{doc_name}.pdf",
                    workflow.output_folder_id
                )
                generated_doc.pdf_file_id = pdf_result['id']
                generated_doc.pdf_url = pdf_result['url']
            
            db.session.add(generated_doc)
            
            # Processar anexo HubSpot se configurado
            self._process_hubspot_attachment(
                workflow=workflow,
                generated_doc=generated_doc,
                source_object_id=source_object_id,
                pdf_bytes=pdf_bytes,
                doc_name=doc_name
            )
            
            # Incrementar contador da organização
            org.increment_document_count()
            
            # Atualizar execução
            end_time = datetime.utcnow()
            execution.status = 'completed'
            execution.completed_at = end_time
            execution.execution_time_ms = int((end_time - start_time).total_seconds() * 1000)
            execution.generated_document_id = generated_doc.id
            
            # Salvar métricas de IA se houver
            if ai_metrics.details:
                execution.ai_metrics = ai_metrics.to_dict()
            
            db.session.commit()
            
            logger.info(f"Documento gerado com sucesso: {generated_doc.id}")
            return generated_doc
            
        except Exception as e:
            logger.error(f"Erro ao gerar documento: {str(e)}")
            
            if execution:
                execution.status = 'failed'
                execution.error_message = str(e)
                execution.completed_at = datetime.utcnow()
                db.session.commit()
            
            raise
    
    def _normalize_hubspot_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normaliza dados do HubSpot movendo properties para o nível raiz.
        
        Os dados do HubSpot vêm no formato:
        {
            'id': '...',
            'properties': {
                'dealname': '...',
                'telefone_do_contato': '...',
                ...
            },
            'associations': {...}
        }
        
        Este método normaliza para:
        {
            'id': '...',
            'dealname': '...',
            'telefone_do_contato': '...',
            'associations': {...}
        }
        
        Args:
            data: Dados do HubSpot com estrutura aninhada
        
        Returns:
            Dados normalizados com properties no nível raiz
        """
        if not isinstance(data, dict):
            return data
        
        # Se não tem 'properties', retorna como está (já normalizado ou outro formato)
        if 'properties' not in data:
            return data
        
        # Criar cópia dos dados
        normalized = data.copy()
        
        # Mesclar properties no nível raiz
        properties = normalized.pop('properties', {})
        if isinstance(properties, dict):
            normalized.update(properties)
        
        # Manter associations no nível raiz para acesso via dot notation
        # (ex: associations.company.name)
        # associations já está em normalized, não precisa fazer nada
        
        return normalized
    
    def _generate_document_name(
        self, 
        template: str, 
        data: Dict, 
        object_type: str
    ) -> str:
        """
        Gera o nome do documento baseado no template de nomeação.
        
        Template suporta tags como:
        - {{company_name}}
        - {{date}} - data atual
        - {{timestamp}} - timestamp atual
        - {{object_type}} - tipo do objeto
        """
        if not template:
            template = "{{object_type}} - {{timestamp}}"
        
        # Adiciona campos especiais
        data_with_meta = {
            **data,
            'date': datetime.utcnow().strftime('%Y-%m-%d'),
            'timestamp': datetime.utcnow().strftime('%Y%m%d_%H%M%S'),
            'object_type': object_type
        }
        
        return TagProcessor.replace_tags(template, data_with_meta)
    
    def _upload_pdf(self, pdf_bytes: bytes, name: str, folder_id: str) -> Dict:
        """Upload do PDF para o Google Drive"""
        from googleapiclient.http import MediaInMemoryUpload
        
        media = MediaInMemoryUpload(pdf_bytes, mimetype='application/pdf')
        
        file_metadata = {
            'name': name,
            'mimeType': 'application/pdf'
        }
        
        if folder_id:
            file_metadata['parents'] = [folder_id]
        
        file = self.google_docs.drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink'
        ).execute()
        
        return {
            'id': file['id'],
            'url': file.get('webViewLink', f"https://drive.google.com/file/d/{file['id']}/view")
        }
    
    def _process_ai_tags(
        self,
        workflow: Workflow,
        source_data: Dict[str, Any],
        metrics: AIGenerationMetrics
    ) -> Dict[str, str]:
        """
        Processa todas as tags AI do workflow.
        
        Args:
            workflow: Workflow com mapeamentos de IA
            source_data: Dados da fonte para montar prompts
            metrics: Objeto para rastrear métricas
        
        Returns:
            Dicionário com {ai:tag_name: texto_gerado}
        """
        from app.services.ai import LLMService, AIGenerationError, AITimeoutError, AIQuotaExceededError, AIInvalidKeyError
        from app.services.ai.utils import get_model_string
        
        replacements = {}
        
        # Buscar mapeamentos de IA do workflow
        ai_mappings = list(workflow.ai_mappings)
        
        if not ai_mappings:
            return replacements
        
        ai_logger.info(f"[AI] Processando {len(ai_mappings)} tags AI para workflow {workflow.id}")
        
        for mapping in ai_mappings:
            start_time = time.time()
            tag_key = f"ai:{mapping.ai_tag}"
            
            try:
                # Buscar API key da conexão
                api_key = self._get_ai_api_key(mapping)
                if not api_key:
                    raise AIInvalidKeyError(
                        "Conexão de IA não configurada ou API key não encontrada",
                        mapping.provider,
                        mapping.model
                    )
                
                # Montar prompt
                prompt = TagProcessor.build_ai_prompt(
                    prompt_template=mapping.prompt_template,
                    source_data=source_data,
                    source_fields=mapping.source_fields
                )
                
                # Gerar texto
                model_string = get_model_string(mapping.provider, mapping.model)
                response = self.llm_service.generate_text(
                    model=model_string,
                    prompt=prompt,
                    api_key=api_key,
                    temperature=mapping.temperature or 0.7,
                    max_tokens=mapping.max_tokens or 1000,
                    timeout=60
                )
                
                # Salvar resultado
                replacements[tag_key] = response.text
                elapsed_ms = (time.time() - start_time) * 1000
                
                # Atualizar métricas
                metrics.add_success(
                    mapping=mapping,
                    time_ms=elapsed_ms,
                    tokens=response.total_tokens,
                    cost=response.estimated_cost_usd
                )
                
                # Atualizar contador de uso do mapping
                mapping.increment_usage()
                
                ai_logger.info(
                    f"[AI] Tag '{mapping.ai_tag}' gerada - "
                    f"tokens={response.total_tokens}, time_ms={elapsed_ms:.0f}"
                )
                
            except (AIQuotaExceededError, AIInvalidKeyError) as e:
                # Erros críticos - propagar para interromper documento
                elapsed_ms = (time.time() - start_time) * 1000
                metrics.add_failure(mapping, str(e), elapsed_ms)
                ai_logger.error(f"[AI] Erro crítico na tag '{mapping.ai_tag}': {e}")
                raise
            
            except AITimeoutError as e:
                # Timeout - usar fallback
                elapsed_ms = (time.time() - start_time) * 1000
                metrics.add_failure(mapping, str(e), elapsed_ms)
                fallback = mapping.fallback_value or f"[Timeout: {mapping.ai_tag}]"
                replacements[tag_key] = fallback
                ai_logger.warning(f"[AI] Timeout na tag '{mapping.ai_tag}', usando fallback")
            
            except AIGenerationError as e:
                # Outros erros de IA - usar fallback
                elapsed_ms = (time.time() - start_time) * 1000
                metrics.add_failure(mapping, str(e), elapsed_ms)
                fallback = mapping.fallback_value or f"[Erro: {mapping.ai_tag}]"
                replacements[tag_key] = fallback
                ai_logger.warning(f"[AI] Erro na tag '{mapping.ai_tag}': {e}")
            
            except Exception as e:
                # Erro inesperado - usar fallback
                elapsed_ms = (time.time() - start_time) * 1000
                metrics.add_failure(mapping, str(e), elapsed_ms)
                fallback = mapping.fallback_value or f"[Erro: {mapping.ai_tag}]"
                replacements[tag_key] = fallback
                ai_logger.error(f"[AI] Erro inesperado na tag '{mapping.ai_tag}': {e}")
        
        return replacements

    def _process_ai_tags_from_config(
        self,
        ai_mappings: List[Dict[str, Any]],
        source_data: Dict[str, Any],
        workflow: Workflow,
        metrics: AIGenerationMetrics
    ) -> Dict[str, str]:
        """
        Processa tags AI a partir de configuração (node.config.ai_mappings).

        Args:
            ai_mappings: Lista de dicts com configuração de AI mappings
            source_data: Dados da fonte para montar prompts
            workflow: Workflow (para buscar connections)
            metrics: Objeto para rastrear métricas

        Returns:
            Dicionário com {ai:tag_name: texto_gerado}
        """
        from app.services.ai import LLMService, AIGenerationError, AITimeoutError, AIQuotaExceededError, AIInvalidKeyError
        from app.services.ai.utils import get_model_string

        replacements = {}

        if not ai_mappings:
            return replacements

        ai_logger.info(f"[AI] Processando {len(ai_mappings)} tags AI (from config) para workflow {workflow.id}")

        for mapping_config in ai_mappings:
            start_time = time.time()
            tag_name = mapping_config.get('ai_tag')
            tag_key = f"ai:{tag_name}"

            try:
                # Buscar API key da conexão
                api_key = self._get_ai_api_key_from_config(mapping_config, workflow.organization_id)
                if not api_key:
                    raise AIInvalidKeyError(
                        "Conexão de IA não configurada ou API key não encontrada",
                        mapping_config.get('provider'),
                        mapping_config.get('model')
                    )

                # Montar prompt
                prompt = TagProcessor.build_ai_prompt(
                    prompt_template=mapping_config.get('prompt_template', ''),
                    source_data=source_data,
                    source_fields=mapping_config.get('source_fields', [])
                )

                # Gerar texto
                provider = mapping_config.get('provider')
                model = mapping_config.get('model')
                model_string = get_model_string(provider, model)
                response = self.llm_service.generate_text(
                    model=model_string,
                    prompt=prompt,
                    api_key=api_key,
                    temperature=mapping_config.get('temperature', 0.7),
                    max_tokens=mapping_config.get('max_tokens', 1000),
                    timeout=60
                )

                # Salvar resultado
                replacements[tag_key] = response.text
                elapsed_ms = (time.time() - start_time) * 1000

                # Atualizar métricas (criar objeto temporário compatível)
                class TempMapping:
                    def __init__(self, config):
                        self.ai_tag = config.get('ai_tag')
                        self.provider = config.get('provider')
                        self.model = config.get('model')
                        self.source_fields = config.get('source_fields', [])

                temp_mapping = TempMapping(mapping_config)
                metrics.add_success(
                    mapping=temp_mapping,
                    time_ms=elapsed_ms,
                    tokens=response.total_tokens,
                    cost=response.estimated_cost_usd
                )

                ai_logger.info(
                    f"[AI] Tag '{tag_name}' gerada - "
                    f"tokens={response.total_tokens}, time_ms={elapsed_ms:.0f}"
                )

            except (AIQuotaExceededError, AIInvalidKeyError) as e:
                elapsed_ms = (time.time() - start_time) * 1000
                fallback = mapping_config.get('fallback_value', f"[Erro: {tag_name}]")
                replacements[tag_key] = fallback
                ai_logger.error(f"[AI] Erro crítico na tag '{tag_name}': {e}")
                raise

            except AITimeoutError as e:
                elapsed_ms = (time.time() - start_time) * 1000
                fallback = mapping_config.get('fallback_value', f"[Timeout: {tag_name}]")
                replacements[tag_key] = fallback
                ai_logger.warning(f"[AI] Timeout na tag '{tag_name}', usando fallback")

            except AIGenerationError as e:
                elapsed_ms = (time.time() - start_time) * 1000
                fallback = mapping_config.get('fallback_value', f"[Erro: {tag_name}]")
                replacements[tag_key] = fallback
                ai_logger.warning(f"[AI] Erro na tag '{tag_name}': {e}")

            except Exception as e:
                elapsed_ms = (time.time() - start_time) * 1000
                fallback = mapping_config.get('fallback_value', f"[Erro: {tag_name}]")
                replacements[tag_key] = fallback
                ai_logger.error(f"[AI] Erro inesperado na tag '{tag_name}': {e}")

        return replacements

    def _get_ai_api_key_from_config(self, mapping_config: Dict[str, Any], organization_id: str) -> Optional[str]:
        """
        Obtém API key descriptografada da conexão de IA a partir de config.

        Args:
            mapping_config: Dict com ai_connection_id
            organization_id: ID da organização

        Returns:
            API key descriptografada ou None
        """
        from app.models import DataSourceConnection
        from app.utils.encryption import decrypt_config

        ai_connection_id = mapping_config.get('ai_connection_id')
        if not ai_connection_id:
            return None

        connection = DataSourceConnection.query.filter_by(
            id=ai_connection_id,
            organization_id=organization_id
        ).first()

        if not connection:
            return None

        decrypted_config = decrypt_config(connection.config)
        return decrypted_config.get('api_key')

    def _get_ai_api_key(self, mapping: Any) -> Optional[str]:
        """
        DEPRECATED: Use _get_ai_api_key_from_config() instead.

        Obtém a API key descriptografada para a conexão de IA.

        Args:
            mapping: Mapeamento de IA (dict ou object) com referência à conexão

        Returns:
            API key descriptografada ou None
        """
        # Suportar tanto dict quanto object
        ai_connection_id = mapping.ai_connection_id if hasattr(mapping, 'ai_connection_id') else mapping.get('ai_connection_id')

        if not ai_connection_id:
            return None

        # Buscar connection manualmente (não há relacionamento no dict)
        from app.models import DataSourceConnection
        connection = DataSourceConnection.query.get(ai_connection_id)
        if not connection:
            return None
        
        credentials = connection.credentials
        if not credentials:
            return None
        
        # Descriptografar se necessário
        if isinstance(credentials, dict) and credentials.get('encrypted'):
            try:
                decrypted = decrypt_credentials(credentials['encrypted'])
                return decrypted.get('api_key')
            except Exception as e:
                ai_logger.error(f"[AI] Erro ao descriptografar credenciais: {e}")
                return None
        
        # Formato direto (não deveria acontecer em produção)
        if isinstance(credentials, dict):
            return credentials.get('api_key')
        
        return None
    
    def _process_hubspot_attachment(
        self,
        workflow: Workflow,
        generated_doc: GeneratedDocument,
        source_object_id: str,
        pdf_bytes: Optional[bytes],
        doc_name: str
    ) -> None:
        """
        Processa anexo do documento no HubSpot se configurado no workflow.
        
        Args:
            workflow: Workflow com configurações
            generated_doc: Documento gerado
            source_object_id: ID do objeto na fonte
            pdf_bytes: Bytes do PDF (None se não foi gerado)
            doc_name: Nome do documento
        """
        # Verificar se anexo HubSpot está habilitado
        post_actions = workflow.post_actions
        if not post_actions or not isinstance(post_actions, dict):
            return
        
        hubspot_config = post_actions.get('hubspot_attachment')
        if not hubspot_config or not hubspot_config.get('enabled'):
            return
        
        # Verificar se há conexão HubSpot configurada
        connection = workflow.source_connection
        if not connection or connection.source_type != 'hubspot':
            logger.warning(f"Workflow {workflow.id} tem anexo HubSpot habilitado mas não tem conexão HubSpot configurada")
            return
        
        # Verificar se PDF foi gerado (necessário para anexo)
        if not pdf_bytes:
            logger.warning(f"Workflow {workflow.id} tem anexo HubSpot habilitado mas PDF não foi gerado")
            return
        
        try:
            from app.services.data_sources.hubspot_attachments import HubSpotAttachmentService
            
            # Criar serviço de anexo
            attachment_service = HubSpotAttachmentService(connection)
            
            # Fazer upload do arquivo
            filename = f"{doc_name}.pdf"
            file_result = attachment_service.upload_file(
                file_bytes=pdf_bytes,
                filename=filename,
                mime_type='application/pdf',
                access='PRIVATE'
            )
            
            # Salvar informações do arquivo no documento
            generated_doc.hubspot_file_id = file_result['id']
            generated_doc.hubspot_file_url = file_result['url']
            
            # Anexar ao objeto
            attachment_type = hubspot_config.get('attachment_type', 'engagement')
            
            if attachment_type == 'engagement':
                # Anexar via engagement (NOTE)
                note_body = hubspot_config.get('note_body', f'Documento gerado: {doc_name}')
                engagement_result = attachment_service.attach_file_to_object(
                    object_type=workflow.source_object_type,
                    object_id=source_object_id,
                    file_id=file_result['id'],
                    note_body=note_body
                )
                generated_doc.hubspot_attachment_id = engagement_result.get('engagement_id')
                
            elif attachment_type == 'property':
                # Atualizar propriedade customizada com URL do arquivo
                property_name = hubspot_config.get('property_name')
                if not property_name:
                    logger.warning(f"Workflow {workflow.id} tem attachment_type='property' mas property_name não configurado")
                else:
                    attachment_service.update_object_property(
                        object_type=workflow.source_object_type,
                        object_id=source_object_id,
                        property_name=property_name,
                        property_value=file_result['url']
                    )
            
            logger.info(
                f"Documento {generated_doc.id} anexado ao HubSpot: "
                f"object_type={workflow.source_object_type}, object_id={source_object_id}, "
                f"file_id={file_result['id']}"
            )
            
        except Exception as e:
            # Não falhar a geração se anexo falhar, apenas logar
            logger.error(
                f"Erro ao anexar documento {generated_doc.id} no HubSpot: {str(e)}",
                exc_info=True
            )
            # Não propagar exceção para não interromper o fluxo de geração

