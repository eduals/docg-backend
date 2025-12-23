"""
HubSpot API Client - Cliente HTTP helper para o HubSpot.
"""

from typing import Dict, Any, Optional, List
import httpx


class HubSpotAPIClient:
    """
    Cliente HTTP helper para chamadas à API do HubSpot.

    Wrapper sobre httpx.AsyncClient com métodos convenientes.
    """

    def __init__(self, http_client: httpx.AsyncClient):
        self.client = http_client
        self.base_url = 'https://api.hubapi.com'

    async def get_contact(self, contact_id: str, properties: List[str] = None) -> Dict[str, Any]:
        """Busca um contato"""
        params = {}
        if properties:
            params['properties'] = ','.join(properties)

        response = await self.client.get(
            f'/crm/v3/objects/contacts/{contact_id}',
            params=params
        )
        response.raise_for_status()
        return response.json()

    async def get_deal(self, deal_id: str, properties: List[str] = None) -> Dict[str, Any]:
        """Busca um deal"""
        params = {}
        if properties:
            params['properties'] = ','.join(properties)

        response = await self.client.get(
            f'/crm/v3/objects/deals/{deal_id}',
            params=params
        )
        response.raise_for_status()
        return response.json()

    async def get_company(self, company_id: str, properties: List[str] = None) -> Dict[str, Any]:
        """Busca uma company"""
        params = {}
        if properties:
            params['properties'] = ','.join(properties)

        response = await self.client.get(
            f'/crm/v3/objects/companies/{company_id}',
            params=params
        )
        response.raise_for_status()
        return response.json()

    async def search_objects(
        self,
        object_type: str,
        query: str = None,
        filters: List[Dict] = None,
        properties: List[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Busca objetos por query ou filtros"""
        type_map = {
            'contact': 'contacts',
            'deal': 'deals',
            'company': 'companies',
        }
        api_type = type_map.get(object_type.lower(), object_type)

        body = {'limit': limit}

        if query:
            body['query'] = query
        if filters:
            body['filterGroups'] = [{'filters': filters}]
        if properties:
            body['properties'] = properties

        response = await self.client.post(
            f'/crm/v3/objects/{api_type}/search',
            json=body
        )
        response.raise_for_status()
        return response.json().get('results', [])

    async def create_object(
        self,
        object_type: str,
        properties: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Cria um objeto"""
        type_map = {
            'contact': 'contacts',
            'deal': 'deals',
            'company': 'companies',
        }
        api_type = type_map.get(object_type.lower(), object_type)

        response = await self.client.post(
            f'/crm/v3/objects/{api_type}',
            json={'properties': properties}
        )
        response.raise_for_status()
        return response.json()

    async def update_object(
        self,
        object_type: str,
        object_id: str,
        properties: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Atualiza um objeto"""
        type_map = {
            'contact': 'contacts',
            'deal': 'deals',
            'company': 'companies',
        }
        api_type = type_map.get(object_type.lower(), object_type)

        response = await self.client.patch(
            f'/crm/v3/objects/{api_type}/{object_id}',
            json={'properties': properties}
        )
        response.raise_for_status()
        return response.json()

    async def get_associations(
        self,
        from_type: str,
        from_id: str,
        to_type: str,
    ) -> List[Dict[str, Any]]:
        """Busca associações de um objeto"""
        type_map = {
            'contact': 'contacts',
            'deal': 'deals',
            'company': 'companies',
        }
        from_api = type_map.get(from_type.lower(), from_type)
        to_api = type_map.get(to_type.lower(), to_type)

        response = await self.client.get(
            f'/crm/v4/objects/{from_api}/{from_id}/associations/{to_api}'
        )
        response.raise_for_status()
        return response.json().get('results', [])
