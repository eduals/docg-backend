from typing import Dict, Any, Optional
import requests
import logging
import time
from .hubspot import HubSpotDataSource
from app.utils.encryption import decrypt_credentials

logger = logging.getLogger(__name__)


class HubSpotAttachmentService:
    """
    Serviço para upload e anexo de arquivos no HubSpot.
    Extende HubSpotDataSource com funcionalidades de upload e anexo.
    """
    
    BASE_URL = "https://api.hubapi.com"
    
    def __init__(self, connection):
        """
        Args:
            connection: DataSourceConnection com credenciais do HubSpot
        """
        self.connection = connection
        
        # Descriptografar credenciais se necessário
        credentials = connection.credentials
        if credentials and isinstance(credentials, dict) and credentials.get('encrypted'):
            try:
                credentials = decrypt_credentials(credentials['encrypted'])
            except Exception as e:
                logger.error(f"Erro ao descriptografar credenciais do HubSpot: {e}")
                raise Exception('Erro ao descriptografar credenciais do HubSpot')
        
        self.access_token = credentials.get('access_token') if credentials else None
        
        if not self.access_token:
            raise Exception('HubSpot access token não configurado')
    
    def _normalize_object_type_for_api(self, object_type: str) -> str:
        """
        Normaliza o tipo de objeto para o formato esperado pela API v3/v4 do HubSpot.
        Converte formas plurais para singulares e padroniza nomes em lowercase.
        
        Args:
            object_type: Tipo do objeto (contacts, contact, companies, company, etc)
        
        Returns:
            Tipo normalizado em lowercase (contact, company, deal, ticket)
        """
        normalization_map = {
            'contact': 'contact',
            'contacts': 'contact',
            'company': 'company',
            'companies': 'company',
            'deal': 'deal',
            'deals': 'deal',
            'ticket': 'ticket',
            'tickets': 'ticket',
            'quote': 'quote',
            'quotes': 'quote',
            'line_item': 'line_item',
            'line_items': 'line_item'
        }
        
        return normalization_map.get(object_type.lower(), object_type.lower())
    
    def upload_file(
        self, 
        file_bytes: bytes, 
        filename: str, 
        mime_type: str = 'application/pdf',
        folder_path: Optional[str] = None,
        access: str = 'PRIVATE'
    ) -> Dict[str, Any]:
        """
        Faz upload de um arquivo para o HubSpot.
        
        Args:
            file_bytes: Conteúdo do arquivo em bytes
            filename: Nome do arquivo
            mime_type: Tipo MIME do arquivo (default: application/pdf)
            folder_path: Caminho da pasta no HubSpot (opcional)
            access: Nível de acesso ('PUBLIC_INDEXABLE' ou 'PRIVATE')
        
        Returns:
            Dict com id, url e outras informações do arquivo
        """
        url = f"{self.BASE_URL}/files/v3/files"
        
        headers = {
            'Authorization': f'Bearer {self.access_token}'
        }
        
        # Preparar dados do multipart form
        files = {
            'file': (filename, file_bytes, mime_type)
        }
        
        data = {
            'access': access
        }
        
        if folder_path:
            data['folderPath'] = folder_path
        
        try:
            response = requests.post(url, headers=headers, files=files, data=data)
            response.raise_for_status()
            
            result = response.json()
            
            return {
                'id': result.get('id'),
                'url': result.get('url'),
                'name': result.get('name'),
                'size': result.get('size'),
                'created_at': result.get('createdAt')
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro ao fazer upload de arquivo no HubSpot: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Resposta do HubSpot: {e.response.text}")
            raise Exception(f'Erro ao fazer upload de arquivo no HubSpot: {str(e)}')
    
    def attach_file_to_object(
        self,
        object_type: str,
        object_id: str,
        file_id: str,
        note_body: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Anexa um arquivo a um objeto do HubSpot criando um engagement do tipo NOTE.
        
        Args:
            object_type: Tipo do objeto (deal, ticket, contact, company, etc)
            object_id: ID do objeto
            file_id: ID do arquivo no HubSpot (retornado por upload_file)
            note_body: Texto opcional para a nota (default: "Documento gerado automaticamente")
        
        Returns:
            Dict com id do engagement criado
        """
        url = f"{self.BASE_URL}/engagements/v1/engagements"
        
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        # Normalizar object_type para o formato esperado pela API de engagements (UPPERCASE)
        object_type_normalized = self._normalize_object_type(object_type)
        
        # Criar payload do engagement conforme estrutura da API v1
        # A API espera: engagement, associations, attachments, metadata
        payload = {
            'engagement': {
                'active': True,
                'type': 'NOTE',
                'timestamp': int(time.time() * 1000)  # timestamp em milissegundos
            },
            'associations': self._build_associations(object_type_normalized, object_id),
            'attachments': [
                {
                    'id': file_id
                }
            ],
            'metadata': {
                'body': note_body if note_body else 'Documento gerado automaticamente'
            }
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            
            result = response.json()
            
            # A resposta pode ter engagement no nível raiz ou dentro de 'engagement'
            engagement = result.get('engagement') or result
            return {
                'engagement_id': engagement.get('id'),
                'created_at': engagement.get('createdAt')
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro ao anexar arquivo ao objeto no HubSpot: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Resposta do HubSpot: {e.response.text}")
            raise Exception(f'Erro ao anexar arquivo ao objeto no HubSpot: {str(e)}')
    
    def update_object_property(
        self,
        object_type: str,
        object_id: str,
        property_name: str,
        property_value: str
    ) -> Dict[str, Any]:
        """
        Atualiza uma propriedade de um objeto no HubSpot.
        Útil para salvar URL do arquivo em propriedade customizada.
        
        Args:
            object_type: Tipo do objeto (deal, ticket, contact, company, etc)
            object_id: ID do objeto
            property_name: Nome da propriedade (ex: 'documento_proposta')
            property_value: Valor da propriedade (ex: URL do arquivo)
        
        Returns:
            Dict com resultado da atualização
        """
        # Normalizar object_type para API v3/v4 (lowercase)
        normalized_type = self._normalize_object_type_for_api(object_type)
        
        # Mapear tipos de objeto para endpoints da API (usando formato correto /crm/v3/...)
        endpoint_map = {
            'contact': 'crm/v3/objects/contacts',
            'company': 'crm/v3/objects/companies',
            'deal': 'crm/v3/objects/deals',
            'ticket': 'crm/v3/objects/tickets',
            'quote': 'crm/v3/objects/quotes',
            'line_item': 'crm/v3/objects/line_items'
        }
        
        endpoint = endpoint_map.get(normalized_type)
        if not endpoint:
            raise Exception(f'Tipo de objeto não suportado: {object_type}')
        
        url = f"{self.BASE_URL}/{endpoint}/{object_id}"
        
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'properties': {
                property_name: property_value
            }
        }
        
        try:
            response = requests.patch(url, headers=headers, json=payload)
            response.raise_for_status()
            
            result = response.json()
            
            return {
                'id': result.get('id'),
                'updated_at': result.get('updatedAt'),
                'properties': result.get('properties', {})
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro ao atualizar propriedade do objeto no HubSpot: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Resposta do HubSpot: {e.response.text}")
            raise Exception(f'Erro ao atualizar propriedade do objeto no HubSpot: {str(e)}')
    
    def _normalize_object_type(self, object_type: str) -> str:
        """Normaliza o tipo de objeto para o formato esperado pela API de engagements"""
        mapping = {
            'contact': 'CONTACT',
            'contacts': 'CONTACT',
            'deal': 'DEAL',
            'deals': 'DEAL',
            'company': 'COMPANY',
            'companies': 'COMPANY',
            'ticket': 'TICKET',
            'tickets': 'TICKET',
            'quote': 'QUOTE',
            'quotes': 'QUOTE',
            'line_item': 'LINE_ITEM',
            'line_items': 'LINE_ITEM'
        }
        
        return mapping.get(object_type.lower(), object_type.upper())
    
    def _build_associations(self, object_type: str, object_id: str) -> Dict[str, list]:
        """
        Constrói o objeto associations conforme esperado pela API de engagements.
        
        Args:
            object_type: Tipo do objeto normalizado (CONTACT, DEAL, etc)
            object_id: ID do objeto
        
        Returns:
            Dict com arrays de IDs conforme estrutura da API
        """
        associations = {
            'contactIds': [],
            'companyIds': [],
            'dealIds': [],
            'ticketIds': [],
            'quoteIds': [],
            'lineItemIds': [],
            'ownerIds': []
        }
        
        # Mapear tipo para o campo correto
        type_to_field = {
            'CONTACT': 'contactIds',
            'COMPANY': 'companyIds',
            'DEAL': 'dealIds',
            'TICKET': 'ticketIds',
            'QUOTE': 'quoteIds',
            'LINE_ITEM': 'lineItemIds'
        }
        
        field_name = type_to_field.get(object_type)
        if field_name:
            associations[field_name] = [object_id]
        
        return associations
    
    def _get_association_type_id(self, object_type: str) -> int:
        """
        Retorna o ID do tipo de associação para o objeto.
        Valores padrão da API do HubSpot.
        (Mantido para compatibilidade, mas não usado na API v1)
        """
        association_map = {
            'CONTACT': 1,
            'COMPANY': 2,
            'DEAL': 3,
            'TICKET': 25,
            'QUOTE': 15,
            'LINE_ITEM': 20
        }
        
        return association_map.get(object_type, 1)

