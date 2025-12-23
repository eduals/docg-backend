"""
Google Drive App - Integração com Google Drive para armazenamento.
"""

from app.apps.base import BaseApp, AuthConfig, AuthType, ActionDefinition, DynamicDataDefinition


class GoogleDriveApp(BaseApp):
    @property
    def name(self) -> str:
        return 'Google Drive'

    @property
    def key(self) -> str:
        return 'google-drive'

    @property
    def icon_url(self) -> str:
        return 'https://ssl.gstatic.com/images/branding/product/1x/drive_2020q4_48dp.png'

    @property
    def description(self) -> str:
        return 'Store and manage files in Google Drive'

    @property
    def base_url(self) -> str:
        return 'https://www.googleapis.com/drive/v3'

    def get_auth_config(self) -> AuthConfig:
        return AuthConfig(
            auth_type=AuthType.OAUTH2,
            oauth2_auth_url='https://accounts.google.com/o/oauth2/v2/auth',
            oauth2_token_url='https://oauth2.googleapis.com/token',
            oauth2_scopes=['https://www.googleapis.com/auth/drive'],
        )

    def _setup(self):
        from .actions import list_files, upload_file, download_file
        from .dynamic_data import list_folders

        self.register_action(ActionDefinition(
            key='list-files',
            name='List Files',
            description='Lists files in a folder',
            handler=list_files.run,
        ))

        self.register_action(ActionDefinition(
            key='upload-file',
            name='Upload File',
            description='Uploads a file to Drive',
            handler=upload_file.run,
        ))

        self.register_action(ActionDefinition(
            key='download-file',
            name='Download File',
            description='Downloads a file from Drive',
            handler=download_file.run,
        ))

        self.register_dynamic_data(DynamicDataDefinition(
            key='list-folders',
            name='List Folders',
            description='Lists folders for selection',
            handler=list_folders.run,
        ))


google_drive_app = GoogleDriveApp()
