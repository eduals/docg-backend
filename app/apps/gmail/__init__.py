"""
Gmail App - Integração com Gmail para envio de emails.
"""

from app.apps.base import BaseApp, AuthConfig, AuthType, ActionDefinition


class GmailApp(BaseApp):
    @property
    def name(self) -> str:
        return 'Gmail'

    @property
    def key(self) -> str:
        return 'gmail'

    @property
    def icon_url(self) -> str:
        return 'https://ssl.gstatic.com/ui/v1/icons/mail/rfr/gmail.ico'

    @property
    def description(self) -> str:
        return 'Send emails via Gmail SMTP'

    def get_auth_config(self) -> AuthConfig:
        return AuthConfig(
            auth_type=AuthType.OAUTH2,
            oauth2_auth_url='https://accounts.google.com/o/oauth2/v2/auth',
            oauth2_token_url='https://oauth2.googleapis.com/token',
            oauth2_scopes=['https://mail.google.com/'],
        )

    def _setup(self):
        from .actions import send_email

        self.register_action(ActionDefinition(
            key='send-email',
            name='Send Email',
            description='Sends an email via Gmail',
            handler=send_email.run,
        ))


gmail_app = GmailApp()
