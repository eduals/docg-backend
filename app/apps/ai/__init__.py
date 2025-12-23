"""AI/LLM App - Integração com múltiplos provedores de IA via LiteLLM."""

from app.apps.base import BaseApp, AuthConfig, AuthType, ActionDefinition


class AIApp(BaseApp):
    @property
    def name(self) -> str:
        return 'AI/LLM'

    @property
    def key(self) -> str:
        return 'ai'

    @property
    def icon_url(self) -> str:
        return 'https://openai.com/favicon.ico'

    @property
    def description(self) -> str:
        return 'Generate text using AI models (OpenAI, Gemini, Anthropic, etc.)'

    def get_auth_config(self) -> AuthConfig:
        return AuthConfig(auth_type=AuthType.API_KEY, api_key_header='Authorization')

    def _setup(self):
        from .actions import generate_text, process_tags
        self.register_action(ActionDefinition(key='generate-text', name='Generate Text', description='Generates text using an AI model', handler=generate_text.run))
        self.register_action(ActionDefinition(key='process-tags', name='Process AI Tags', description='Processes {{ai:tag}} in text', handler=process_tags.run))


ai_app = AIApp()
