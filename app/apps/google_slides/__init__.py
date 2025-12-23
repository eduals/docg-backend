"""
Google Slides App - Integração com Google Slides para apresentações.
"""

from app.apps.base import BaseApp, AuthConfig, AuthType, ActionDefinition


class GoogleSlidesApp(BaseApp):
    @property
    def name(self) -> str:
        return 'Google Slides'

    @property
    def key(self) -> str:
        return 'google-slides'

    @property
    def icon_url(self) -> str:
        return 'https://ssl.gstatic.com/docs/presentations/images/favicon5.ico'

    @property
    def description(self) -> str:
        return 'Create and edit presentations in Google Slides'

    @property
    def base_url(self) -> str:
        return 'https://slides.googleapis.com/v1'

    def get_auth_config(self) -> AuthConfig:
        return AuthConfig(
            auth_type=AuthType.OAUTH2,
            oauth2_auth_url='https://accounts.google.com/o/oauth2/v2/auth',
            oauth2_token_url='https://oauth2.googleapis.com/token',
            oauth2_scopes=[
                'https://www.googleapis.com/auth/presentations',
                'https://www.googleapis.com/auth/drive',
            ],
        )

    def _setup(self):
        from .actions import copy_template, replace_tags, export_pdf

        self.register_action(ActionDefinition(
            key='copy-template',
            name='Copy Template',
            description='Creates a copy of a Google Slides template',
            handler=copy_template.run,
        ))

        self.register_action(ActionDefinition(
            key='replace-tags',
            name='Replace Tags',
            description='Replaces {{tags}} in a presentation',
            handler=replace_tags.run,
        ))

        self.register_action(ActionDefinition(
            key='export-pdf',
            name='Export as PDF',
            description='Exports presentation as PDF',
            handler=export_pdf.run,
        ))


google_slides_app = GoogleSlidesApp()
