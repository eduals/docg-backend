"""Storage App - Integração com DigitalOcean Spaces (S3 compatible)."""

from app.apps.base import BaseApp, AuthConfig, AuthType, ActionDefinition


class StorageApp(BaseApp):
    @property
    def name(self) -> str:
        return 'Storage'

    @property
    def key(self) -> str:
        return 'storage'

    @property
    def icon_url(self) -> str:
        return 'https://www.digitalocean.com/favicon.ico'

    @property
    def description(self) -> str:
        return 'File storage with DigitalOcean Spaces (S3 compatible)'

    def get_auth_config(self) -> AuthConfig:
        return AuthConfig(auth_type=AuthType.API_KEY)

    def _setup(self):
        from .actions import upload_file, download_file, generate_url
        self.register_action(ActionDefinition(key='upload-file', name='Upload File', description='Uploads a file to storage', handler=upload_file.run))
        self.register_action(ActionDefinition(key='download-file', name='Download File', description='Downloads a file from storage', handler=download_file.run))
        self.register_action(ActionDefinition(key='generate-url', name='Generate URL', description='Generates a signed URL', handler=generate_url.run))


storage_app = StorageApp()
