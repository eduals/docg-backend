"""
HubSpot Associations Helper

Fornece métodos para buscar objetos associados no HubSpot.
Usado para suportar sintaxe como {{trigger.deal.associated.contacts}}.

Referência:
- API v4: GET /crm/v4/objects/{fromObjectType}/{fromObjectId}/associations/{toObjectType}
- Association Types: https://developers.hubspot.com/docs/api/crm/associations
"""

from typing import Dict, Any, List, Optional
import httpx
import logging

logger = logging.getLogger(__name__)


# Mapeamento de tipos de objetos para plural (usado na API)
OBJECT_TYPE_MAP = {
    'contact': 'contacts',
    'contacts': 'contacts',
    'deal': 'deals',
    'deals': 'deals',
    'company': 'companies',
    'companies': 'companies',
    'ticket': 'tickets',
    'tickets': 'tickets',
    'line_item': 'line_items',
    'line_items': 'line_items',
    'product': 'products',
    'products': 'products',
}

# Tipos de associação comuns (para referência)
ASSOCIATION_TYPE_IDS = {
    'contact_to_company': 1,
    'company_to_contact': 2,
    'deal_to_contact': 3,
    'contact_to_deal': 4,
    'deal_to_company': 5,
    'company_to_deal': 6,
    'ticket_to_contact': 15,
    'contact_to_ticket': 16,
    'ticket_to_company': 25,
    'company_to_ticket': 26,
    'deal_to_line_item': 19,
    'line_item_to_deal': 20,
}


class AssociationsHelper:
    """
    Helper para buscar associações do HubSpot.

    Exemplo:
        helper = AssociationsHelper(http_client)

        # Buscar contatos associados a um deal
        contacts = await helper.get_associated_objects('deal', deal_id, 'contact')

        # Buscar company de um contato
        companies = await helper.get_associated_objects('contact', contact_id, 'company')

        # Buscar line items de um deal (com dados completos)
        line_items = await helper.get_associated_objects_with_data('deal', deal_id, 'line_item')
    """

    def __init__(self, http_client: httpx.AsyncClient):
        self.client = http_client

    async def get_associated_object_ids(
        self,
        from_type: str,
        from_id: str,
        to_type: str,
    ) -> List[str]:
        """
        Busca IDs de objetos associados.

        Args:
            from_type: Tipo do objeto de origem (contact, deal, etc)
            from_id: ID do objeto de origem
            to_type: Tipo do objeto de destino

        Returns:
            Lista de IDs dos objetos associados
        """
        from_api = OBJECT_TYPE_MAP.get(from_type.lower(), from_type)
        to_api = OBJECT_TYPE_MAP.get(to_type.lower(), to_type)

        try:
            response = await self.client.get(
                f'/crm/v4/objects/{from_api}/{from_id}/associations/{to_api}'
            )

            if response.status_code == 200:
                results = response.json().get('results', [])
                return [str(r.get('toObjectId')) for r in results]

            return []

        except Exception as e:
            logger.warning(f"Error fetching associations {from_type}/{from_id} -> {to_type}: {e}")
            return []

    async def get_associated_objects(
        self,
        from_type: str,
        from_id: str,
        to_type: str,
        properties: List[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Busca objetos associados com seus dados.

        Args:
            from_type: Tipo do objeto de origem
            from_id: ID do objeto de origem
            to_type: Tipo do objeto de destino
            properties: Lista de propriedades a retornar (opcional)

        Returns:
            Lista de objetos associados com dados
        """
        object_ids = await self.get_associated_object_ids(from_type, from_id, to_type)

        if not object_ids:
            return []

        to_api = OBJECT_TYPE_MAP.get(to_type.lower(), to_type)
        objects = []

        for obj_id in object_ids:
            try:
                params = {}
                if properties:
                    params['properties'] = ','.join(properties)

                response = await self.client.get(
                    f'/crm/v3/objects/{to_api}/{obj_id}',
                    params=params
                )

                if response.status_code == 200:
                    data = response.json()
                    objects.append({
                        'id': data.get('id'),
                        **data.get('properties', {}),
                        '_raw': data
                    })

            except Exception as e:
                logger.warning(f"Error fetching {to_type} {obj_id}: {e}")

        return objects

    async def get_first_associated_object(
        self,
        from_type: str,
        from_id: str,
        to_type: str,
        properties: List[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Busca o primeiro objeto associado.

        Útil para associações 1:1 como deal -> company.

        Args:
            from_type: Tipo do objeto de origem
            from_id: ID do objeto de origem
            to_type: Tipo do objeto de destino
            properties: Lista de propriedades a retornar

        Returns:
            Objeto associado ou None
        """
        objects = await self.get_associated_objects(from_type, from_id, to_type, properties)
        return objects[0] if objects else None

    async def expand_associations(
        self,
        object_type: str,
        object_data: Dict[str, Any],
        association_types: List[str] = None,
    ) -> Dict[str, Any]:
        """
        Expande um objeto com seus dados associados.

        Args:
            object_type: Tipo do objeto
            object_data: Dados do objeto (deve ter 'id')
            association_types: Tipos de associação a expandir

        Returns:
            Objeto com campo 'associated' contendo objetos relacionados
        """
        object_id = object_data.get('id')
        if not object_id:
            return object_data

        # Associações padrão por tipo de objeto
        default_associations = {
            'contact': ['company', 'deal'],
            'deal': ['contact', 'company', 'line_item'],
            'company': ['contact', 'deal'],
            'ticket': ['contact', 'company'],
        }

        types_to_expand = association_types or default_associations.get(object_type.lower(), [])

        associated = {}
        for assoc_type in types_to_expand:
            objects = await self.get_associated_objects(object_type, object_id, assoc_type)

            # Usar plural para o nome da chave
            key = OBJECT_TYPE_MAP.get(assoc_type, assoc_type + 's')
            associated[key] = objects

        return {
            **object_data,
            'associated': associated
        }

    async def create_association(
        self,
        from_type: str,
        from_id: str,
        to_type: str,
        to_id: str,
        association_type_id: int = None,
    ) -> bool:
        """
        Cria uma associação entre dois objetos.

        Args:
            from_type: Tipo do objeto de origem
            from_id: ID do objeto de origem
            to_type: Tipo do objeto de destino
            to_id: ID do objeto de destino
            association_type_id: ID do tipo de associação (opcional)

        Returns:
            True se criada com sucesso
        """
        from_api = OBJECT_TYPE_MAP.get(from_type.lower(), from_type)
        to_api = OBJECT_TYPE_MAP.get(to_type.lower(), to_type)

        # Determinar association type ID se não fornecido
        if association_type_id is None:
            key = f'{from_type.lower()}_to_{to_type.lower()}'
            association_type_id = ASSOCIATION_TYPE_IDS.get(key)

        body = [
            {
                'associationCategory': 'HUBSPOT_DEFINED',
                'associationTypeId': association_type_id
            }
        ] if association_type_id else []

        try:
            response = await self.client.put(
                f'/crm/v4/objects/{from_api}/{from_id}/associations/{to_api}/{to_id}',
                json=body
            )
            return response.status_code in (200, 201)

        except Exception as e:
            logger.warning(f"Error creating association: {e}")
            return False

    async def remove_association(
        self,
        from_type: str,
        from_id: str,
        to_type: str,
        to_id: str,
    ) -> bool:
        """
        Remove uma associação entre dois objetos.

        Args:
            from_type: Tipo do objeto de origem
            from_id: ID do objeto de origem
            to_type: Tipo do objeto de destino
            to_id: ID do objeto de destino

        Returns:
            True se removida com sucesso
        """
        from_api = OBJECT_TYPE_MAP.get(from_type.lower(), from_type)
        to_api = OBJECT_TYPE_MAP.get(to_type.lower(), to_type)

        try:
            response = await self.client.delete(
                f'/crm/v4/objects/{from_api}/{from_id}/associations/{to_api}/{to_id}'
            )
            return response.status_code in (200, 204)

        except Exception as e:
            logger.warning(f"Error removing association: {e}")
            return False


# Funções helper standalone para uso simples

async def get_deal_contacts(
    http_client: httpx.AsyncClient,
    deal_id: str,
    properties: List[str] = None,
) -> List[Dict[str, Any]]:
    """Busca contatos associados a um deal."""
    helper = AssociationsHelper(http_client)
    return await helper.get_associated_objects('deal', deal_id, 'contact', properties)


async def get_deal_company(
    http_client: httpx.AsyncClient,
    deal_id: str,
    properties: List[str] = None,
) -> Optional[Dict[str, Any]]:
    """Busca a empresa associada a um deal."""
    helper = AssociationsHelper(http_client)
    return await helper.get_first_associated_object('deal', deal_id, 'company', properties)


async def get_deal_line_items(
    http_client: httpx.AsyncClient,
    deal_id: str,
    properties: List[str] = None,
) -> List[Dict[str, Any]]:
    """Busca line items de um deal."""
    helper = AssociationsHelper(http_client)
    default_props = properties or ['name', 'price', 'quantity', 'amount', 'hs_sku']
    return await helper.get_associated_objects('deal', deal_id, 'line_item', default_props)


async def get_contact_company(
    http_client: httpx.AsyncClient,
    contact_id: str,
    properties: List[str] = None,
) -> Optional[Dict[str, Any]]:
    """Busca a empresa associada a um contato."""
    helper = AssociationsHelper(http_client)
    return await helper.get_first_associated_object('contact', contact_id, 'company', properties)


async def get_contact_deals(
    http_client: httpx.AsyncClient,
    contact_id: str,
    properties: List[str] = None,
) -> List[Dict[str, Any]]:
    """Busca deals associados a um contato."""
    helper = AssociationsHelper(http_client)
    return await helper.get_associated_objects('contact', contact_id, 'deal', properties)
