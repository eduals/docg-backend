"""Outlook App - Integração com Outlook/Microsoft 365 para envio de emails."""

from app.apps.base import BaseApp, AuthConfig, AuthType, ActionDefinition


class OutlookApp(BaseApp):
    @property
    def name(self) -> str:
        return 'Outlook'

    @property
    def key(self) -> str:
        return 'outlook'

    @property
    def icon_url(self) -> str:
        return 'https://www.microsoft.com/favicon.ico'

    @property
    def description(self) -> str:
        return 'Send emails via Microsoft Outlook/365'

    @property
    def base_url(self) -> str:
        return 'https://graph.microsoft.com/v1.0'

    def get_auth_config(self) -> AuthConfig:
        return AuthConfig(
            auth_type=AuthType.OAUTH2,
            oauth2_auth_url='https://login.microsoftonline.com/common/oauth2/v2.0/authorize',
            oauth2_token_url='https://login.microsoftonline.com/common/oauth2/v2.0/token',
            oauth2_scopes=['Mail.Send', 'offline_access'],
        )

    def _setup(self):
        from .actions import send_email
        self.register_action(ActionDefinition(key='send-email', name='Send Email', description='Sends an email via Outlook', handler=send_email.run))


outlook_app = OutlookApp()
