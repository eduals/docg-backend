"""
Microsoft PowerPoint App - Integração com Microsoft PowerPoint via Graph API.
"""

from app.apps.base import BaseApp, AuthConfig, AuthType, ActionDefinition


class MicrosoftPowerPointApp(BaseApp):
    @property
    def name(self) -> str:
        return 'Microsoft PowerPoint'

    @property
    def key(self) -> str:
        return 'microsoft-powerpoint'

    @property
    def icon_url(self) -> str:
        return 'https://www.microsoft.com/favicon.ico'

    @property
    def description(self) -> str:
        return 'Create and edit PowerPoint presentations via Microsoft 365'

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

        self.register_action(ActionDefinition(key='copy-template', name='Copy Template', description='Creates a copy of a PowerPoint template', handler=copy_template.run))
        self.register_action(ActionDefinition(key='replace-tags', name='Replace Tags', description='Replaces {{tags}} in a presentation', handler=replace_tags.run))
        self.register_action(ActionDefinition(key='export-pdf', name='Export as PDF', description='Exports presentation as PDF', handler=export_pdf.run))


microsoft_powerpoint_app = MicrosoftPowerPointApp()
