from typing import Dict, Any, List
import requests
import logging
from .base import BaseDataSource

logger = logging.getLogger(__name__)

class HubSpotDataSource(BaseDataSource):
    """
    Conector para buscar dados do HubSpot.
    """
    
    BASE_URL = "https://api.hubapi.com"
    
    def __init__(self, connection):
        super().__init__(connection)
        self.access_token = connection.credentials.get('access_token') if connection.credentials else None
        self.portal_id = connection.config.get('portal_id') if connection.config else None
    
    def _normalize_object_type(self, object_type: str) -> str:
        """
        Normaliza o tipo de objeto para o formato esperado pela API do HubSpot.
        Converte formas plurais para singulares e padroniza nomes.
        
        Args:
            object_type: Tipo do objeto (contacts, contact, companies, company, etc)
        
        Returns:
            Tipo normalizado (contact, company, deal, ticket)
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
    
    def get_object_data(self, object_type: str, object_id: str, additional_properties: List[str] = None) -> Dict[str, Any]:
        """
        Busca dados de um objeto específico do HubSpot.
        
        Args:
            object_type: Tipo do objeto (contacts, deals, companies, tickets, quotes, line_items)
            object_id: ID do objeto
            additional_properties: Lista opcional de propriedades adicionais a buscar
        
        Returns:
            Dict com os dados do objeto, incluindo propriedades e associações
        """
        if not self.access_token:
            raise Exception('HubSpot access token não configurado')
        
        # Normalizar tipo de objeto
        normalized_type = self._normalize_object_type(object_type)
        
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
        
        # Combinar propriedades padrão com adicionais
        default_props = self._get_default_properties(object_type)
        if additional_properties:
            # Converter string de propriedades padrão em lista
            default_props_list = default_props.split(',') if default_props != '*' else []
            # Adicionar propriedades adicionais (removendo duplicatas)
            all_properties = list(set(default_props_list + additional_properties))
            # Se tinha '*', manter '*', senão juntar com vírgula
            if default_props == '*':
                properties_param = '*'
            else:
                properties_param = ','.join(all_properties)
        else:
            properties_param = default_props
        
        # Buscar propriedades e associações
        params = {
            'properties': properties_param,
            'associations': self._get_default_associations(object_type)
        }
        
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            # Normalizar estrutura de dados
            normalized = {
                'id': data.get('id'),
                'properties': data.get('properties', {}),
                'associations': {}
            }
            
            # Processar associações
            if 'associations' in data:
                for assoc_type, assoc_data in data['associations'].items():
                    results = assoc_data.get('results', [])
                    if results:
                        # Buscar detalhes das associações
                        normalized['associations'][assoc_type] = self._fetch_associations(
                            object_type, object_id, assoc_type
                        )
            
            return normalized
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro ao buscar objeto do HubSpot: {str(e)}")
            raise Exception(f'Erro ao buscar dados do HubSpot: {str(e)}')
    
    def _fetch_associations(self, object_type: str, object_id: str, association_type: str) -> List[Dict]:
        """Busca detalhes de objetos associados usando API v4"""
        try:
            # Normalizar tipos de objeto
            normalized_from_type = self._normalize_object_type(object_type)
            normalized_to_type = self._normalize_object_type(association_type)
            
            # Usar endpoint correto da API v4 para buscar associações individuais
            # Formato: /crm/v4/objects/{fromObjectType}/{fromObjectId}/associations/{toObjectType}
            url = f"{self.BASE_URL}/crm/v4/objects/{normalized_from_type}/{object_id}/associations/{normalized_to_type}"
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(url, headers=headers)
            if response.ok:
                data = response.json()
                # A resposta da API v4 retorna objetos com toObjectId
                results = data.get('results', [])
                # Extrair IDs dos objetos associados
                associated_ids = []
                for result in results:
                    to_object_id = result.get('toObjectId')
                    if to_object_id:
                        associated_ids.append(to_object_id)
                return associated_ids
            
            return []
            
        except Exception as e:
            logger.warning(f"Erro ao buscar associações: {str(e)}")
            return []
    
    def _get_default_properties(self, object_type: str) -> str:
        """Retorna propriedades padrão para cada tipo de objeto"""
        property_map = {
            'contact': 'firstname,lastname,email,phone,company,lifecyclestage,hs_lead_status',
            'contacts': 'firstname,lastname,email,phone,company,lifecyclestage,hs_lead_status',
            'deal': 'dealname,amount,dealstage,closedate,pipeline,dealtype',
            'deals': 'dealname,amount,dealstage,closedate,pipeline,dealtype',
            'company': 'name,domain,industry,type,phone,address',
            'companies': 'name,domain,industry,type,phone,address',
            'ticket': 'subject,content,priority,status,hs_pipeline_stage',
            'tickets': 'subject,content,priority,status,hs_pipeline_stage',
            'quote': 'hs_title,hs_amount,hs_expiration_date,hs_status',
            'quotes': 'hs_title,hs_amount,hs_expiration_date,hs_status',
            'line_item': 'name,price,quantity,amount,hs_recurring_billing_period',
            'line_items': 'name,price,quantity,amount,hs_recurring_billing_period'
        }
        
        return property_map.get(object_type.lower(), '*')
    
    def _get_default_associations(self, object_type: str) -> List[str]:
        """Retorna associações padrão para cada tipo de objeto"""
        assoc_map = {
            'contact': ['companies', 'deals'],
            'contacts': ['companies', 'deals'],
            'deal': ['contacts', 'companies', 'line_items'],
            'deals': ['contacts', 'companies', 'line_items'],
            'company': ['contacts', 'deals'],
            'companies': ['contacts', 'deals'],
            'ticket': ['contacts', 'companies'],
            'tickets': ['contacts', 'companies']
        }
        
        return assoc_map.get(object_type.lower(), [])
    
    def list_objects(self, object_type: str, filters: Dict = None) -> list:
        """
        Lista objetos do HubSpot.
        
        Args:
            object_type: Tipo do objeto
            filters: Filtros opcionais
        
        Returns:
            Lista de objetos
        """
        if not self.access_token:
            raise Exception('HubSpot access token não configurado')
        
        # Normalizar tipo de objeto
        normalized_type = self._normalize_object_type(object_type)
        
        # Mapear tipos de objeto para endpoints da API (usando formato correto /crm/v3/...)
        endpoint_map = {
            'contact': 'crm/v3/objects/contacts',
            'company': 'crm/v3/objects/companies',
            'deal': 'crm/v3/objects/deals',
            'ticket': 'crm/v3/objects/tickets'
        }
        
        endpoint = endpoint_map.get(normalized_type)
        if not endpoint:
            raise Exception(f'Tipo de objeto não suportado: {object_type}')
        
        url = f"{self.BASE_URL}/{endpoint}"
        
        params = {
            'properties': self._get_default_properties(object_type),
            'limit': filters.get('limit', 100) if filters else 100
        }
        
        if filters and 'after' in filters:
            params['after'] = filters['after']
        
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            return data.get('results', [])
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro ao listar objetos do HubSpot: {str(e)}")
            raise Exception(f'Erro ao listar objetos do HubSpot: {str(e)}')
    
    def test_connection(self) -> bool:
        """
        Testa se a conexão com HubSpot está funcionando.
        
        Returns:
            True se conexão OK, False caso contrário
        """
        if not self.access_token:
            return False
        
        try:
            url = f"{self.BASE_URL}/integrations/v1/me"
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(url, headers=headers, timeout=5)
            return response.ok
            
        except Exception as e:
            logger.error(f"Erro ao testar conexão HubSpot: {str(e)}")
            return False
    
    def get_object_properties(self, object_type: str) -> List[Dict[str, Any]]:
        """
        Busca todas as propriedades de um tipo de objeto do HubSpot.
        
        Args:
            object_type: Tipo do objeto (deal, contact, company, ticket)
        
        Returns:
            Lista de propriedades com name, label, type, options
        """
        if not self.access_token:
            raise Exception('HubSpot access token não configurado')
        
        # Normalizar tipo de objeto
        normalized_type = self._normalize_object_type(object_type)
        
        # Mapear tipos de objeto para endpoints da API Properties (usando formato correto /crm/v3/properties/...)
        endpoint_map = {
            'contact': 'crm/v3/properties/contact',
            'company': 'crm/v3/properties/company',
            'deal': 'crm/v3/properties/deal',
            'ticket': 'crm/v3/properties/ticket'
        }
        
        endpoint = endpoint_map.get(normalized_type)
        if not endpoint:
            raise Exception(f'Tipo de objeto não suportado: {object_type}')
        
        url = f"{self.BASE_URL}/{endpoint}"
        
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            results = data.get('results', [])
            
            # Normalizar propriedades
            properties = []
            for prop in results:
                # Filtrar apenas propriedades visíveis e não arquivadas
                if prop.get('archived', False):
                    continue
                
                properties.append({
                    'name': prop.get('name', ''),
                    'label': prop.get('label', prop.get('name', '')),
                    'type': prop.get('type', 'string'),
                    'options': prop.get('options')  # Para campos enum
                })
            
            return properties
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro ao buscar propriedades do HubSpot: {str(e)}")
            raise Exception(f'Erro ao buscar propriedades do HubSpot: {str(e)}')

