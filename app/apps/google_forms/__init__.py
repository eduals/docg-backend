"""
Google Forms App - Integração com Google Forms como fonte de dados.
"""

from app.apps.base import BaseApp, AuthConfig, AuthType, TriggerDefinition


class GoogleFormsApp(BaseApp):
    @property
    def name(self) -> str:
        return 'Google Forms'

    @property
    def key(self) -> str:
        return 'google-forms'

    @property
    def icon_url(self) -> str:
        return 'https://ssl.gstatic.com/docs/forms/device_home/android_192.png'

    @property
    def description(self) -> str:
        return 'Collect data via Google Forms responses'

    @property
    def base_url(self) -> str:
        return 'https://forms.googleapis.com/v1'

    def get_auth_config(self) -> AuthConfig:
        return AuthConfig(
            auth_type=AuthType.OAUTH2,
            oauth2_auth_url='https://accounts.google.com/o/oauth2/v2/auth',
            oauth2_token_url='https://oauth2.googleapis.com/token',
            oauth2_scopes=[
                'https://www.googleapis.com/auth/forms.responses.readonly',
                'https://www.googleapis.com/auth/drive.readonly',
            ],
        )

    def _setup(self):
        from .triggers import new_response

        self.register_trigger(TriggerDefinition(
            key='new-response',
            name='New Form Response',
            description='Triggers when a new form response is submitted',
            handler=new_response.run,
            trigger_type='webhook',
        ))


google_forms_app = GoogleFormsApp()
