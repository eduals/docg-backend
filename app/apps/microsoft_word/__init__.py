"""
Microsoft Word App - Integração com Microsoft Word via Graph API.
"""

from app.apps.base import BaseApp, AuthConfig, AuthType, ActionDefinition


class MicrosoftWordApp(BaseApp):
    @property
    def name(self) -> str:
        return 'Microsoft Word'

    @property
    def key(self) -> str:
        return 'microsoft-word'

    @property
    def icon_url(self) -> str:
        return 'https://www.microsoft.com/favicon.ico'

    @property
    def description(self) -> str:
        return 'Create and edit Word documents via Microsoft 365'

    @property
    def base_url(self) -> str:
        return 'https://graph.microsoft.com/v1.0'

    def get_auth_config(self) -> AuthConfig:
        return AuthConfig(
            auth_type=AuthType.OAUTH2,
            oauth2_auth_url='https://login.microsoftonline.com/common/oauth2/v2.0/authorize',
            oauth2_token_url='https://login.microsoftonline.com/common/oauth2/v2.0/token',
            oauth2_scopes=['Files.ReadWrite.All', 'offline_access'],
        )

    def _setup(self):
        from .actions import copy_template, replace_tags, export_pdf

        self.register_action(ActionDefinition(
            key='copy-template',
            name='Copy Template',
            description='Creates a copy of a Word template',
            handler=copy_template.run,
        ))

        self.register_action(ActionDefinition(
            key='replace-tags',
            name='Replace Tags',
            description='Replaces {{tags}} in a document',
            handler=replace_tags.run,
        ))

        self.register_action(ActionDefinition(
            key='export-pdf',
            name='Export as PDF',
            description='Exports document as PDF',
            handler=export_pdf.run,
        ))


microsoft_word_app = MicrosoftWordApp()
