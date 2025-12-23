"""
Google Docs App - Integração com Google Docs para geração de documentos.

Este app fornece:
- Autenticação OAuth2 com Google
- Actions para copiar templates, substituir tags, exportar PDF

NOTA: Importa funcionalidades do serviço existente.
"""

from app.apps.base import BaseApp, AuthConfig, AuthType, ActionDefinition


class GoogleDocsApp(BaseApp):
    """
    App Google Docs para geração de documentos.
    """

    @property
    def name(self) -> str:
        return 'Google Docs'

    @property
    def key(self) -> str:
        return 'google-docs'

    @property
    def icon_url(self) -> str:
        return 'https://ssl.gstatic.com/docs/documents/images/kix-favicon7.ico'

    @property
    def description(self) -> str:
        return 'Create and edit documents in Google Docs'

    @property
    def base_url(self) -> str:
        return 'https://docs.googleapis.com/v1'

    def get_auth_config(self) -> AuthConfig:
        """Configuração OAuth2 do Google"""
        return AuthConfig(
            auth_type=AuthType.OAUTH2,
            oauth2_auth_url='https://accounts.google.com/o/oauth2/v2/auth',
            oauth2_token_url='https://oauth2.googleapis.com/token',
            oauth2_scopes=[
                'https://www.googleapis.com/auth/documents',
                'https://www.googleapis.com/auth/drive',
            ],
        )

    def _setup(self):
        """Registra actions"""
        from .actions import copy_template, replace_tags, export_pdf

        self.register_action(ActionDefinition(
            key='copy-template',
            name='Copy Template',
            description='Creates a copy of a Google Docs template',
            handler=copy_template.run,
        ))

        self.register_action(ActionDefinition(
            key='replace-tags',
            name='Replace Tags',
            description='Replaces {{tags}} in a document with values',
            handler=replace_tags.run,
        ))

        self.register_action(ActionDefinition(
            key='export-pdf',
            name='Export as PDF',
            description='Exports document as PDF',
            handler=export_pdf.run,
        ))


google_docs_app = GoogleDocsApp()
