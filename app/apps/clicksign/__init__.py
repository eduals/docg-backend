"""
ClickSign App - Integração com ClickSign para assinaturas eletrônicas.

Este app fornece:
- Autenticação via API Key
- Actions para criar envelopes, adicionar signatários, enviar para assinatura
- Webhooks para status de assinatura

NOTA: Este app importa funcionalidades do adapter existente.
"""

from app.apps.base import BaseApp, AuthConfig, AuthType, ActionDefinition


class ClickSignApp(BaseApp):
    """
    App ClickSign para assinaturas eletrônicas.

    Funcionalidades:
    - API Key authentication
    - Create signature envelopes
    - Add signers
    - Send for signature
    - Webhook callbacks
    """

    @property
    def name(self) -> str:
        return 'ClickSign'

    @property
    def key(self) -> str:
        return 'clicksign'

    @property
    def icon_url(self) -> str:
        return 'https://www.clicksign.com/wp-content/uploads/2020/07/favicon.png'

    @property
    def description(self) -> str:
        return 'Brazilian electronic signature platform'

    @property
    def base_url(self) -> str:
        return 'https://app.clicksign.com/api/v1'

    @property
    def documentation_url(self) -> str:
        return 'https://developers.clicksign.com/'

    def get_auth_config(self) -> AuthConfig:
        """Configuração de API Key do ClickSign"""
        return AuthConfig(
            auth_type=AuthType.API_KEY,
            api_key_query_param='access_token',
        )

    def _setup(self):
        """Registra actions"""
        from .actions import create_envelope, add_signer, send_for_signature

        self.register_action(ActionDefinition(
            key='create-envelope',
            name='Create Envelope',
            description='Creates a new signature envelope',
            handler=create_envelope.run,
            input_schema={
                'type': 'object',
                'properties': {
                    'document_url': {'type': 'string'},
                    'document_name': {'type': 'string'},
                },
                'required': ['document_url'],
            },
        ))

        self.register_action(ActionDefinition(
            key='add-signer',
            name='Add Signer',
            description='Adds a signer to an envelope',
            handler=add_signer.run,
            input_schema={
                'type': 'object',
                'properties': {
                    'envelope_id': {'type': 'string'},
                    'email': {'type': 'string'},
                    'name': {'type': 'string'},
                },
                'required': ['envelope_id', 'email', 'name'],
            },
        ))

        self.register_action(ActionDefinition(
            key='send-for-signature',
            name='Send for Signature',
            description='Sends an envelope for signature',
            handler=send_for_signature.run,
            input_schema={
                'type': 'object',
                'properties': {
                    'envelope_id': {'type': 'string'},
                    'message': {'type': 'string'},
                },
                'required': ['envelope_id'],
            },
        ))

    async def test_connection(self, connection_id: str = None, credentials: dict = None) -> dict:
        """Testa conexão com ClickSign"""
        try:
            # Import do adapter existente
            from app.services.integrations.signature.clicksign import ClickSignAdapter
            from app.models import DataSourceConnection

            if connection_id:
                connection = DataSourceConnection.query.get(connection_id)
                if connection:
                    adapter = ClickSignAdapter(connection.get_credentials())
                    result = adapter.test_connection()
                    return result

            return {'success': False, 'message': 'Connection not found'}
        except Exception as e:
            return {'success': False, 'message': str(e)}


# Instância singleton do app
clicksign_app = ClickSignApp()
