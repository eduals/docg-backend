"""
Google Forms DataSource - Busca dados de formulários do Google Forms.
"""
from typing import Dict, Any, List, Optional
import logging
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .base import BaseDataSource

logger = logging.getLogger(__name__)


class GoogleFormsDataSource(BaseDataSource):
    """
    Conector para buscar dados do Google Forms.
    
    Usa GoogleOAuthToken da organização para autenticação.
    """
    
    def __init__(self, connection=None, credentials=None):
        """
        Inicializa DataSource.
        
        Args:
            connection: DataSourceConnection (opcional, para compatibilidade)
            credentials: Credentials do Google (obrigatório)
        """
        super().__init__(connection)
        self.credentials = credentials
    
    def _get_forms_service(self):
        """Cria serviço do Google Forms API"""
        if not self.credentials:
            raise Exception('Credenciais Google não configuradas')
        return build('forms', 'v1', credentials=self.credentials)
    
    def _get_drive_service(self):
        """Cria serviço do Google Drive API (para listar formulários)"""
        if not self.credentials:
            raise Exception('Credenciais Google não configuradas')
        return build('drive', 'v3', credentials=self.credentials)
    
    def list_forms(self) -> List[Dict[str, Any]]:
        """
        Lista formulários do usuário.
        
        Usa Google Drive API para buscar arquivos tipo 'application/vnd.google-apps.form'.
        
        Returns:
            Lista de formulários: [{id, title, url, created_time, modified_time}]
        """
        try:
            drive_service = self._get_drive_service()
            
            # Buscar arquivos tipo Google Form
            results = drive_service.files().list(
                q="mimeType='application/vnd.google-apps.form' and trashed=false",
                fields="files(id, name, webViewLink, createdTime, modifiedTime)",
                pageSize=100,
                orderBy='modifiedTime desc'
            ).execute()
            
            forms = []
            for file in results.get('files', []):
                forms.append({
                    'id': file.get('id'),
                    'title': file.get('name', ''),
                    'url': file.get('webViewLink', ''),
                    'created_time': file.get('createdTime', ''),
                    'modified_time': file.get('modifiedTime', '')
                })
            
            return forms
            
        except HttpError as e:
            logger.error(f"Erro ao listar formulários: {str(e)}")
            raise Exception(f'Erro ao listar formulários: {str(e)}')
    
    def get_form_fields(self, form_id: str) -> List[Dict[str, Any]]:
        """
        Lista campos/propriedades de um formulário.
        
        Args:
            form_id: ID do formulário
        
        Returns:
            Lista de campos: [{question_id, title, type, required}]
        """
        try:
            forms_service = self._get_forms_service()
            
            # Buscar informações do formulário
            form = forms_service.forms().get(formId=form_id).execute()
            
            fields = []
            items = form.get('items', [])
            
            for item in items:
                # Extrair informações da questão
                question_item = item.get('questionItem', {})
                if question_item:
                    question = question_item.get('question', {})
                    if question:
                        question_id = question.get('questionId', '')
                        title = item.get('title', question.get('title', ''))
                        question_type = question.get('type', {}).get('type', 'text')
                        required = question.get('required', False)
                        
                        fields.append({
                            'question_id': question_id,
                            'title': title,
                            'type': question_type,
                            'required': required
                        })
                
                # Verificar se há sub-itens (grupos, seções)
                if 'itemGroup' in item:
                    group_items = item.get('itemGroup', {}).get('items', [])
                    for group_item in group_items:
                        group_question = group_item.get('questionItem', {}).get('question', {})
                        if group_question:
                            question_id = group_question.get('questionId', '')
                            title = group_item.get('title', group_question.get('title', ''))
                            question_type = group_question.get('type', {}).get('type', 'text')
                            required = group_question.get('required', False)
                            
                            fields.append({
                                'question_id': question_id,
                                'title': title,
                                'type': question_type,
                                'required': required
                            })
            
            return fields
            
        except HttpError as e:
            logger.error(f"Erro ao buscar campos do formulário: {str(e)}")
            raise Exception(f'Erro ao buscar campos do formulário: {str(e)}')
    
    def get_form_responses(
        self, 
        form_id: str, 
        response_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Busca respostas do formulário.
        
        Args:
            form_id: ID do formulário
            response_id: ID da resposta específica (opcional)
        
        Returns:
            Dict com source_data mapeado: {campo1: valor1, campo2: valor2, ...}
        """
        try:
            forms_service = self._get_forms_service()
            
            # Buscar informações do formulário para mapear question_id -> campo
            form_info = forms_service.forms().get(formId=form_id).execute()
            
            # Criar mapeamento question_id -> nome do campo
            question_map = {}
            for item in form_info.get('items', []):
                question_item = item.get('questionItem', {})
                if question_item:
                    question = question_item.get('question', {})
                    if question:
                        question_id = question.get('questionId', '')
                        title = item.get('title', question.get('title', ''))
                        if question_id and title:
                            # Normalizar nome do campo (lowercase, substituir espaços por underscore)
                            field_name = title.lower().replace(' ', '_').replace('-', '_')
                            # Remover caracteres especiais
                            field_name = ''.join(c for c in field_name if c.isalnum() or c == '_')
                            question_map[question_id] = field_name
                
                # Verificar sub-itens
                if 'itemGroup' in item:
                    group_items = item.get('itemGroup', {}).get('items', [])
                    for group_item in group_items:
                        group_question = group_item.get('questionItem', {}).get('question', {})
                        if group_question:
                            question_id = group_question.get('questionId', '')
                            title = group_item.get('title', group_question.get('title', ''))
                            if question_id and title:
                                field_name = title.lower().replace(' ', '_').replace('-', '_')
                                field_name = ''.join(c for c in field_name if c.isalnum() or c == '_')
                                question_map[question_id] = field_name
            
            # Buscar resposta
            if response_id:
                # Resposta específica
                response = forms_service.forms().responses().get(
                    formId=form_id,
                    responseId=response_id
                ).execute()
            else:
                # Última resposta
                responses_result = forms_service.forms().responses().list(formId=form_id).execute()
                responses = responses_result.get('responses', [])
                if not responses:
                    raise ValueError('Nenhuma resposta encontrada no formulário')
                response = responses[-1]  # Última resposta
            
            # Mapear respostas para source_data
            source_data = {}
            answers = response.get('answers', {})
            
            for question_id, answer in answers.items():
                # Obter nome do campo do mapeamento
                field_name = question_map.get(question_id, f'field_{question_id}')
                
                # Extrair valor baseado no tipo de resposta
                value = None
                if 'textAnswers' in answer:
                    text_answers = answer.get('textAnswers', {}).get('answers', [])
                    if text_answers:
                        value = text_answers[0].get('value', '')
                elif 'fileUploadAnswers' in answer:
                    file_answers = answer.get('fileUploadAnswers', {}).get('answers', [])
                    if file_answers:
                        value = file_answers[0].get('fileId', '')
                elif 'choiceAnswers' in answer:
                    choice_answers = answer.get('choiceAnswers', {}).get('answers', [])
                    if choice_answers:
                        value = choice_answers[0].get('value', '')
                elif 'scaleAnswers' in answer:
                    scale_answer = answer.get('scaleAnswers', {}).get('answers', [])
                    if scale_answer:
                        value = scale_answer[0].get('value', '')
                elif 'dateAnswers' in answer:
                    date_answers = answer.get('dateAnswers', {}).get('answers', [])
                    if date_answers:
                        value = date_answers[0].get('value', {}).get('year', '') + '-' + \
                                str(date_answers[0].get('value', {}).get('month', '')).zfill(2) + '-' + \
                                str(date_answers[0].get('value', {}).get('day', '')).zfill(2)
                elif 'timeAnswers' in answer:
                    time_answers = answer.get('timeAnswers', {}).get('answers', [])
                    if time_answers:
                        time_value = time_answers[0].get('value', {})
                        value = f"{time_value.get('hours', 0):02d}:{time_value.get('minutes', 0):02d}"
                else:
                    # Fallback: converter para string
                    value = str(answer)
                
                if value is not None:
                    source_data[field_name] = value
            
            return source_data
            
        except HttpError as e:
            logger.error(f"Erro ao buscar respostas do formulário: {str(e)}")
            raise Exception(f'Erro ao buscar respostas do formulário: {str(e)}')
    
    def get_object_data(self, object_type: str, object_id: str) -> Dict[str, Any]:
        """
        Busca dados de um objeto específico (implementação de BaseDataSource).
        
        Args:
            object_type: 'form_response'
            object_id: Formato 'form_id_response_id' ou apenas 'response_id'
        
        Returns:
            Dict com source_data
        """
        # object_id pode ser 'form_id_response_id' ou apenas 'response_id'
        # Se contém underscore, separar
        if '_' in object_id:
            parts = object_id.split('_', 1)
            form_id = parts[0]
            response_id = parts[1] if len(parts) > 1 else None
        else:
            # Se não tem form_id, precisamos buscar do config do node
            # Por enquanto, assumir que form_id vem do config
            raise ValueError('form_id necessário para buscar resposta específica')
        
        return self.get_form_responses(form_id, response_id)
    
    def list_objects(self, object_type: str, filters: Dict = None) -> list:
        """
        Lista objetos da fonte (implementação de BaseDataSource).
        
        Para Google Forms, lista formulários.
        """
        if object_type == 'form':
            return self.list_forms()
        else:
            raise ValueError(f'Tipo de objeto não suportado: {object_type}')
    
    def get_object_properties(self, form_id: str) -> List[Dict[str, Any]]:
        """
        Retorna campos do formulário para mapeamento.
        
        Args:
            form_id: ID do formulário
        
        Returns:
            Lista de propriedades: [{question_id, title, type, required}]
        """
        return self.get_form_fields(form_id)
    
    def test_connection(self) -> bool:
        """
        Testa se a conexão com Google Forms está funcionando.
        
        Returns:
            True se conexão OK, False caso contrário
        """
        if not self.credentials:
            return False
        
        try:
            # Tentar listar formulários
            forms = self.list_forms()
            return True
        except Exception as e:
            logger.error(f"Erro ao testar conexão Google Forms: {str(e)}")
            return False
