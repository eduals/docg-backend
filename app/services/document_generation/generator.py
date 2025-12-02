from typing import Dict, Any, Optional, List
from datetime import datetime
import logging
import time

from app.database import db
from app.models import (
    Workflow, GeneratedDocument, Template, 
    WorkflowFieldMapping, Organization, WorkflowExecution,
    AIGenerationMapping
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
    
    def add_success(self, mapping: 'AIGenerationMapping', time_ms: float, tokens: int = 0, cost: float = 0.0):
        self.details.append({
            'tag': mapping.ai_tag,
            'provider': mapping.provider,
            'model': mapping.model,
            'time_ms': round(time_ms),
            'tokens': tokens,
            'cost_usd': cost,
            'status': 'success'
        })
        self.total_time_ms += time_ms
        self.total_tokens += tokens
        self.total_cost += cost
        self.successful += 1
    
    def add_failure(self, mapping: 'AIGenerationMapping', error: str, time_ms: float = 0):
        self.details.append({
            'tag': mapping.ai_tag,
            'provider': mapping.provider,
            'model': mapping.model,
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
    
    def _get_ai_api_key(self, mapping: AIGenerationMapping) -> Optional[str]:
        """
        Obtém a API key descriptografada para a conexão de IA.
        
        Args:
            mapping: Mapeamento de IA com referência à conexão
        
        Returns:
            API key descriptografada ou None
        """
        if not mapping.ai_connection_id:
            return None
        
        connection = mapping.ai_connection
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

