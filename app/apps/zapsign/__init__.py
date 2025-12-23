"""
ZapSign App - Integração com ZapSign para assinaturas eletrônicas.

Este app fornece:
- Autenticação via API Key
- Actions para criar documentos e adicionar signatários
- Webhooks para status de assinatura
"""

from app.apps.base import BaseApp, AuthConfig, AuthType, ActionDefinition


class ZapSignApp(BaseApp):
    """
    App ZapSign para assinaturas eletrônicas brasileiras.
    """

    @property
    def name(self) -> str:
        return 'ZapSign'

    @property
    def key(self) -> str:
        return 'zapsign'

    @property
    def icon_url(self) -> str:
        return 'https://zapsign.com.br/favicon.ico'

    @property
    def description(self) -> str:
        return 'Brazilian electronic signature platform'

    @property
    def base_url(self) -> str:
        return 'https://api.zapsign.com.br/api/v1'

    def get_auth_config(self) -> AuthConfig:
        """Configuração de API Key do ZapSign"""
        return AuthConfig(
            auth_type=AuthType.API_KEY,
            api_key_header='Authorization',
        )

    def _setup(self):
        """Registra actions"""
        from .actions import create_document

        self.register_action(ActionDefinition(
            key='create-document',
            name='Create Document',
            description='Creates a new document for signature',
            handler=create_document.run,
        ))

    async def test_connection(self, connection_id: str = None, credentials: dict = None) -> dict:
        """Testa conexão com ZapSign"""
        try:
            from app.services.integrations.signature.zapsign import ZapSignAdapter
            from app.models import DataSourceConnection

            if connection_id:
                connection = DataSourceConnection.query.get(connection_id)
                if connection:
                    adapter = ZapSignAdapter(connection.get_credentials())
                    result = adapter.test_connection()
                    return result

            return {'success': False, 'message': 'Connection not found'}
        except Exception as e:
            return {'success': False, 'message': str(e)}


zapsign_app = ZapSignApp()
