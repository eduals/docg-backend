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
        
        # Mapear tipos de objeto para endpoints da API
        endpoint_map = {
            'contact': 'contacts/v3/objects/contacts',
            'contacts': 'contacts/v3/objects/contacts',
            'deal': 'crm/v3/objects/deals',
            'deals': 'crm/v3/objects/deals',
            'company': 'crm/v3/objects/companies',
            'companies': 'crm/v3/objects/companies',
            'ticket': 'crm/v3/objects/tickets',
            'tickets': 'crm/v3/objects/tickets',
            'quote': 'crm/v3/objects/quotes',
            'quotes': 'crm/v3/objects/quotes',
            'line_item': 'crm/v3/objects/line_items',
            'line_items': 'crm/v3/objects/line_items'
        }
        
        endpoint = endpoint_map.get(object_type.lower())
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
        """Busca detalhes de objetos associados"""
        try:
            # Mapear tipos de associação
            assoc_map = {
                'contacts': 'contacts/v3/objects/contacts',
                'companies': 'crm/v3/objects/companies',
                'deals': 'crm/v3/objects/deals',
                'tickets': 'crm/v3/objects/tickets',
                'quotes': 'crm/v3/objects/quotes',
                'line_items': 'crm/v3/objects/line_items'
            }
            
            endpoint = assoc_map.get(association_type)
            if not endpoint:
                return []
            
            url = f"{self.BASE_URL}/crm/v4/objects/{object_type}/{object_id}/associations/{association_type}"
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(url, headers=headers)
            if response.ok:
                data = response.json()
                # Retornar lista de IDs associados
                return [item.get('id') for item in data.get('results', [])]
            
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
        
        endpoint_map = {
            'contact': 'contacts/v3/objects/contacts',
            'contacts': 'contacts/v3/objects/contacts',
            'deal': 'crm/v3/objects/deals',
            'deals': 'crm/v3/objects/deals',
            'company': 'crm/v3/objects/companies',
            'companies': 'crm/v3/objects/companies'
        }
        
        endpoint = endpoint_map.get(object_type.lower())
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

