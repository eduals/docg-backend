"""
HubSpot App - Integração com HubSpot CRM.

Este app fornece:
- Autenticação OAuth2 com HubSpot
- Actions para criar/atualizar contatos, deals, companies
- Triggers para eventos de CRM
- Dados dinâmicos (properties, objects)

NOTA: Este app importa funcionalidades dos serviços existentes
para manter backward compatibility.
"""

from app.apps.base import BaseApp, AuthConfig, AuthType, ActionDefinition, TriggerDefinition, DynamicDataDefinition


class HubSpotApp(BaseApp):
    """
    App HubSpot para integração com o CRM.

    Funcionalidades:
    - OAuth2 authentication
    - Fetch contact/deal/company data
    - Create/update CRM objects
    - Webhooks para eventos
    - Property listing
    """

    @property
    def name(self) -> str:
        return 'HubSpot'

    @property
    def key(self) -> str:
        return 'hubspot'

    @property
    def icon_url(self) -> str:
        return 'https://www.hubspot.com/hubfs/HubSpot_Logos/HubSpot-Inversed-Favicon.png'

    @property
    def description(self) -> str:
        return 'CRM platform for marketing, sales, and customer service'

    @property
    def base_url(self) -> str:
        return 'https://api.hubapi.com'

    @property
    def documentation_url(self) -> str:
        return 'https://developers.hubspot.com/docs/api/overview'

    def get_auth_config(self) -> AuthConfig:
        """Configuração OAuth2 do HubSpot"""
        return AuthConfig(
            auth_type=AuthType.OAUTH2,
            oauth2_auth_url='https://app.hubspot.com/oauth/authorize',
            oauth2_token_url='https://api.hubapi.com/oauth/v1/token',
            oauth2_scopes=[
                'crm.objects.contacts.read',
                'crm.objects.contacts.write',
                'crm.objects.deals.read',
                'crm.objects.deals.write',
                'crm.objects.companies.read',
                'crm.objects.companies.write',
                'crm.schemas.contacts.read',
                'crm.schemas.deals.read',
                'crm.schemas.companies.read',
                'files',
            ],
        )

    def _setup(self):
        """Registra actions, triggers e dynamic data"""
        # Import local para evitar circular imports
        from .actions import get_object, create_contact, update_contact, create_deal, update_deal, attach_file
        from .triggers import new_deal, new_contact, updated_deal
        from .dynamic_data import list_properties, list_objects

        # Registrar actions
        self.register_action(ActionDefinition(
            key='get-object',
            name='Get Object',
            description='Fetches data from a HubSpot object (contact, deal, company)',
            handler=get_object.run,
            input_schema={
                'type': 'object',
                'properties': {
                    'object_type': {'type': 'string', 'enum': ['contact', 'deal', 'company', 'ticket']},
                    'object_id': {'type': 'string'},
                    'properties': {'type': 'array', 'items': {'type': 'string'}},
                },
                'required': ['object_type', 'object_id'],
            },
        ))

        self.register_action(ActionDefinition(
            key='create-contact',
            name='Create Contact',
            description='Creates a new contact in HubSpot',
            handler=create_contact.run,
            input_schema={
                'type': 'object',
                'properties': {
                    'email': {'type': 'string'},
                    'firstname': {'type': 'string'},
                    'lastname': {'type': 'string'},
                    'properties': {'type': 'object'},
                },
                'required': ['email'],
            },
        ))

        self.register_action(ActionDefinition(
            key='update-contact',
            name='Update Contact',
            description='Updates an existing contact in HubSpot',
            handler=update_contact.run,
            input_schema={
                'type': 'object',
                'properties': {
                    'contact_id': {'type': 'string'},
                    'properties': {'type': 'object'},
                },
                'required': ['contact_id', 'properties'],
            },
        ))

        self.register_action(ActionDefinition(
            key='create-deal',
            name='Create Deal',
            description='Creates a new deal in HubSpot',
            handler=create_deal.run,
        ))

        self.register_action(ActionDefinition(
            key='update-deal',
            name='Update Deal',
            description='Updates an existing deal in HubSpot',
            handler=update_deal.run,
        ))

        self.register_action(ActionDefinition(
            key='attach-file',
            name='Attach File',
            description='Attaches a file to a HubSpot object',
            handler=attach_file.run,
        ))

        # Registrar triggers
        self.register_trigger(TriggerDefinition(
            key='new-deal',
            name='New Deal',
            description='Triggers when a new deal is created',
            handler=new_deal.run,
            trigger_type='webhook',
        ))

        self.register_trigger(TriggerDefinition(
            key='new-contact',
            name='New Contact',
            description='Triggers when a new contact is created',
            handler=new_contact.run,
            trigger_type='webhook',
        ))

        self.register_trigger(TriggerDefinition(
            key='updated-deal',
            name='Deal Updated',
            description='Triggers when a deal is updated',
            handler=updated_deal.run,
            trigger_type='webhook',
        ))

        # Registrar dynamic data
        self.register_dynamic_data(DynamicDataDefinition(
            key='list-properties',
            name='List Properties',
            description='Lists all properties for an object type',
            handler=list_properties.run,
            depends_on=['object_type'],
        ))

        self.register_dynamic_data(DynamicDataDefinition(
            key='list-objects',
            name='List Objects',
            description='Lists objects of a specific type',
            handler=list_objects.run,
            depends_on=['object_type'],
        ))

    async def test_connection(self, connection_id: str = None, credentials: dict = None) -> dict:
        """Testa conexão com HubSpot"""
        try:
            http_client = await self.create_http_client(connection_id)
            response = await http_client.get('/crm/v3/objects/contacts', params={'limit': 1})
            await http_client.aclose()

            if response.status_code == 200:
                return {'success': True, 'message': 'Connected to HubSpot successfully'}
            else:
                return {'success': False, 'message': f'HubSpot returned status {response.status_code}'}
        except Exception as e:
            return {'success': False, 'message': str(e)}


# Instância singleton do app
hubspot_app = HubSpotApp()
