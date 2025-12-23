"""
BaseApp - Classe base para todos os apps modulares.

Similar à estrutura do Automatisch, cada app é um módulo auto-contido
com autenticação, actions, triggers e dados dinâmicos.

Estrutura típica de um app:
    app/apps/{app_name}/
    ├── __init__.py          # App class principal
    ├── auth.py              # Configuração de autenticação
    ├── actions/             # Actions do app
    │   ├── __init__.py
    │   └── {action_name}.py
    ├── triggers/            # Triggers do app (opcional)
    │   ├── __init__.py
    │   └── {trigger_name}.py
    ├── dynamic_data/        # Dados dinâmicos (opcional)
    │   ├── __init__.py
    │   └── {data_name}.py
    └── common/              # Helpers compartilhados (opcional)
        └── {helper}.py
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Type, Callable, Union
from enum import Enum
from dataclasses import dataclass, field, asdict
import httpx
import logging

logger = logging.getLogger(__name__)


class AuthType(Enum):
    """Tipos de autenticação suportados"""
    NONE = 'none'
    API_KEY = 'api_key'
    OAUTH2 = 'oauth2'
    BASIC = 'basic'
    BEARER = 'bearer'
    CUSTOM = 'custom'


@dataclass
class AuthConfig:
    """Configuração de autenticação do app"""
    auth_type: AuthType
    # OAuth2
    oauth2_auth_url: Optional[str] = None
    oauth2_token_url: Optional[str] = None
    oauth2_scopes: List[str] = field(default_factory=list)
    oauth2_extra_params: Dict[str, str] = field(default_factory=dict)
    # API Key
    api_key_header: Optional[str] = None
    api_key_query_param: Optional[str] = None
    # Custom
    custom_auth_handler: Optional[Callable] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'auth_type': self.auth_type.value,
            'oauth2_auth_url': self.oauth2_auth_url,
            'oauth2_token_url': self.oauth2_token_url,
            'oauth2_scopes': self.oauth2_scopes,
            'oauth2_extra_params': self.oauth2_extra_params,
            'api_key_header': self.api_key_header,
            'api_key_query_param': self.api_key_query_param,
        }


# =============================================================================
# ARGUMENT SCHEMA - Estrutura rica para campos de input (estilo Automatisch)
# =============================================================================

class ArgumentType(Enum):
    """Tipos de campos suportados para UI"""
    STRING = 'string'
    NUMBER = 'number'
    BOOLEAN = 'boolean'
    DROPDOWN = 'dropdown'
    MULTILINE = 'multiline'
    CODE = 'code'
    JSON = 'json'
    DATE = 'date'
    DATETIME = 'datetime'
    FILE = 'file'
    HIDDEN = 'hidden'


@dataclass
class DynamicDataSource:
    """
    Fonte de dados dinâmicos para dropdowns.

    Exemplo de uso:
        source=DynamicDataSource(
            key='listChannels',
            depends_on=['workspace_id']  # Precisa desse campo preenchido primeiro
        )
    """
    key: str                                    # 'listChannels', 'listProperties'
    type: str = 'query'                         # 'query' ou 'static'
    depends_on: List[str] = field(default_factory=list)  # Campos necessários

    def to_dict(self) -> Dict[str, Any]:
        return {
            'key': self.key,
            'type': self.type,
            'depends_on': self.depends_on,
        }


@dataclass
class DynamicFieldsSource:
    """
    Fonte de campos dinâmicos/condicionais.

    Campos adicionais que aparecem baseado em seleções anteriores.

    Exemplo:
        additional_fields=DynamicFieldsSource(
            key='signatureTypeFields',
            depends_on=['signature_type']
        )
    """
    key: str                                    # 'signatureTypeFields'
    depends_on: List[str] = field(default_factory=list)  # Campos que controlam

    def to_dict(self) -> Dict[str, Any]:
        return {
            'key': self.key,
            'depends_on': self.depends_on,
        }


class DynamicFieldsDefinition:
    """
    Definição de campos dinâmicos que dependem de valores selecionados.

    Similar ao additionalFields do Automatisch, permite que apps definam
    campos que aparecem dinamicamente baseado em seleções anteriores.

    Exemplo de implementação:
        class HubSpotObjectFieldsDefinition(DynamicFieldsDefinition):
            key = 'objectFields'
            depends_on = ['object_type']

            async def get_fields(
                self,
                http_client: httpx.AsyncClient,
                context: Dict[str, Any]
            ) -> List[ActionArgument]:
                object_type = context.get('object_type')
                if not object_type:
                    return []

                # Buscar propriedades do objeto no HubSpot
                response = await http_client.get(
                    f'/crm/v3/properties/{object_type}'
                )
                properties = response.json()['results']

                return [
                    ActionArgument(
                        key=prop['name'],
                        label=prop['label'],
                        type=ArgumentType.STRING,
                        required=False,
                        variables=True
                    )
                    for prop in properties
                ]
    """
    key: str = ''
    depends_on: List[str] = []

    async def get_fields(
        self,
        http_client: Optional['httpx.AsyncClient'],
        context: Dict[str, Any]
    ) -> List['ActionArgument']:
        """
        Retorna lista de campos dinâmicos baseado no contexto.

        Args:
            http_client: Cliente HTTP autenticado (se precisar fazer chamadas)
            context: Dict com valores selecionados que este campo depende

        Returns:
            Lista de ActionArgument para renderizar na UI
        """
        raise NotImplementedError("Subclasses must implement get_fields()")

    def to_dict(self) -> Dict[str, Any]:
        return {
            'key': self.key,
            'depends_on': self.depends_on,
        }


@dataclass
class ActionArgument:
    """
    Definição de um campo de input para action/trigger.

    Similar ao Automatisch arguments, define metadados ricos para UI:
    - Tipos de campo (dropdown, textarea, code editor)
    - Fonte de dados dinâmicos
    - Se aceita variáveis {{step.x.y}}
    - Campos condicionais

    Exemplo:
        ActionArgument(
            key='channel',
            label='Channel',
            type=ArgumentType.DROPDOWN,
            required=True,
            variables=True,
            source=DynamicDataSource(key='listChannels')
        )
    """
    key: str                                    # 'channel', 'message'
    label: str                                  # 'Channel', 'Message'
    type: ArgumentType = ArgumentType.STRING    # Tipo do campo
    required: bool = False
    description: str = ''
    placeholder: str = ''
    variables: bool = True                      # Aceita {{step.x.y}}
    default_value: Any = None

    # Para dropdowns com opções estáticas
    options: Optional[List[Dict[str, Any]]] = None  # [{'label': 'Yes', 'value': 'yes'}]

    # Para dropdowns com dados dinâmicos
    source: Optional[DynamicDataSource] = None

    # Campos condicionais
    depends_on: Optional[str] = None            # Campo que controla visibilidade
    show_when: Optional[Dict[str, Any]] = None  # Condição para mostrar: {'field': 'value'}
    additional_fields: Optional[DynamicFieldsSource] = None  # Campos extras baseado neste

    # Validação
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    pattern: Optional[str] = None               # Regex para validação

    def to_dict(self) -> Dict[str, Any]:
        result = {
            'key': self.key,
            'label': self.label,
            'type': self.type.value if isinstance(self.type, ArgumentType) else self.type,
            'required': self.required,
            'description': self.description,
            'placeholder': self.placeholder,
            'variables': self.variables,
            'default_value': self.default_value,
        }
        if self.options:
            result['options'] = self.options
        if self.source:
            result['source'] = self.source.to_dict()
        if self.depends_on:
            result['depends_on'] = self.depends_on
        if self.show_when:
            result['show_when'] = self.show_when
        if self.additional_fields:
            result['additional_fields'] = self.additional_fields.to_dict()
        if self.min_length is not None:
            result['min_length'] = self.min_length
        if self.max_length is not None:
            result['max_length'] = self.max_length
        if self.min_value is not None:
            result['min_value'] = self.min_value
        if self.max_value is not None:
            result['max_value'] = self.max_value
        if self.pattern:
            result['pattern'] = self.pattern
        return result


# =============================================================================
# ACTION RESULT - Output padronizado de todas as actions
# =============================================================================

@dataclass
class ActionResult:
    """
    Resultado padronizado de todas as actions.

    Similar ao $.setActionItem() do Automatisch, padroniza como
    actions retornam dados para que próximos steps possam acessar.

    Exemplo:
        return ActionResult(
            raw=api_response,
            data={
                'id': api_response['id'],
                'email': api_response['properties']['email']
            }
        )

    Próximo step acessa:
        {{step.{stepId}.id}}
        {{step.{stepId}.raw.properties.name}}
    """
    raw: Any                                    # Dados brutos da API
    data: Dict[str, Any] = field(default_factory=dict)  # Dados mapeados
    metadata: Optional[Dict[str, Any]] = None   # Info extra (pagination, etc)

    def __getitem__(self, key: str) -> Any:
        """Permite acesso via result['field']"""
        if key in self.data:
            return self.data[key]
        if isinstance(self.raw, dict):
            return self.raw.get(key)
        return getattr(self.raw, key, None)

    def get(self, key: str, default: Any = None) -> Any:
        """Acesso com valor default"""
        try:
            value = self[key]
            return value if value is not None else default
        except (KeyError, AttributeError):
            return default

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dict (para serialização)"""
        return {
            'raw': self.raw if isinstance(self.raw, dict) else str(self.raw),
            'data': self.data,
            'metadata': self.metadata,
        }


# =============================================================================
# ACTION/TRIGGER DEFINITIONS (existentes, atualizados)
# =============================================================================

@dataclass
class ActionDefinition:
    """Definição de uma action do app"""
    key: str
    name: str
    description: str
    handler: Callable
    # NOVO: Schema rico de arguments (estilo Automatisch)
    arguments: List[ActionArgument] = field(default_factory=list)
    # Legado: mantido para compatibilidade
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None
    requires_connection: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            'key': self.key,
            'name': self.name,
            'description': self.description,
            'requires_connection': self.requires_connection,
            'arguments': [arg.to_dict() for arg in self.arguments],
            'input_schema': self.input_schema,
            'output_schema': self.output_schema,
        }

    def get_argument(self, key: str) -> Optional[ActionArgument]:
        """Retorna um argument pelo key"""
        for arg in self.arguments:
            if arg.key == key:
                return arg
        return None


@dataclass
class TriggerDefinition:
    """Definição de um trigger do app"""
    key: str
    name: str
    description: str
    handler: Callable
    trigger_type: str = 'webhook'  # 'webhook', 'polling', 'subscription'
    # NOVO: Schema rico de arguments
    arguments: List[ActionArgument] = field(default_factory=list)
    # Legado: mantido para compatibilidade
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'key': self.key,
            'name': self.name,
            'description': self.description,
            'trigger_type': self.trigger_type,
            'arguments': [arg.to_dict() for arg in self.arguments],
            'input_schema': self.input_schema,
            'output_schema': self.output_schema,
        }

    def get_argument(self, key: str) -> Optional[ActionArgument]:
        """Retorna um argument pelo key"""
        for arg in self.arguments:
            if arg.key == key:
                return arg
        return None


@dataclass
class DynamicDataDefinition:
    """Definição de dados dinâmicos do app"""
    key: str
    name: str
    description: str
    handler: Callable
    depends_on: List[str] = field(default_factory=list)  # Parâmetros necessários

    def to_dict(self) -> Dict[str, Any]:
        return {
            'key': self.key,
            'name': self.name,
            'description': self.description,
            'depends_on': self.depends_on,
        }


# =============================================================================
# EXECUTION CONTEXT ($) - Objeto de contexto padronizado para actions
# =============================================================================

class EarlyExitError(Exception):
    """Exceção para encerrar execução antecipadamente"""
    def __init__(self, reason: str = None):
        self.reason = reason
        super().__init__(reason or "Early exit requested")


@dataclass
class AuthContext:
    """Contexto de autenticação"""
    id: str                                     # ID da conexão
    data: Dict[str, Any]                        # Credenciais decriptografadas

    def get(self, key: str, default: Any = None) -> Any:
        """Acesso a credenciais"""
        return self.data.get(key, default)


@dataclass
class AppContext:
    """Metadados do app"""
    key: str
    name: str
    base_url: Optional[str] = None


@dataclass
class FlowContext:
    """Metadados do workflow"""
    id: str
    name: str
    organization_id: str


@dataclass
class StepContext:
    """Contexto do step atual"""
    id: str
    app_key: str
    action_key: str
    position: int
    parameters: Dict[str, Any]  # JÁ COMPUTADOS ({{step.x.y}} substituídos)


@dataclass
class ExecutionMetadata:
    """Metadados da execução"""
    id: str
    test_run: bool = False
    until_step: Optional[str] = None

    def exit(self, reason: str = None):
        """Encerra execução antecipadamente"""
        raise EarlyExitError(reason)

    def should_stop(self, current_step_id: str) -> bool:
        """Verifica se deve parar no step atual"""
        return self.until_step and current_step_id == self.until_step


@dataclass
class TriggerOutput:
    """Output do trigger"""
    data: List[Any] = field(default_factory=list)

    def push(self, item: Any):
        """Adiciona item ao output"""
        self.data.append(item)


@dataclass
class ActionOutput:
    """Output da action atual"""
    data: Any = None


@dataclass
class Datastore:
    """
    Storage persistente key-value por organização.

    Permite que actions armazenem dados entre execuções.

    Escopos:
    - organization: Dados compartilhados por toda organização
    - workflow: Dados específicos de um workflow
    - execution: Dados específicos de uma execução
    """
    organization_id: str
    scope: str = 'organization'  # 'organization', 'workflow', 'execution'
    scope_id: Optional[str] = None  # workflow_id ou execution_id
    _cache: Dict[str, Any] = field(default_factory=dict)

    async def get(self, key: str) -> Any:
        """Obtém valor do datastore"""
        # Cache local primeiro
        cache_key = f"{self.scope}:{self.scope_id}:{key}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Buscar do banco
        from app.models.datastore import WorkflowDatastore
        value = WorkflowDatastore.get_value(
            organization_id=self.organization_id,
            key=key,
            scope=self.scope,
            scope_id=self.scope_id
        )

        if value is not None:
            self._cache[cache_key] = value

        return value

    async def set(self, key: str, value: Any, ttl_seconds: int = None):
        """
        Salva valor no datastore.

        Args:
            key: Chave do valor
            value: Valor a salvar
            ttl_seconds: Tempo de vida em segundos (opcional)
        """
        from app.models.datastore import WorkflowDatastore
        WorkflowDatastore.set_value(
            organization_id=self.organization_id,
            key=key,
            value=value,
            scope=self.scope,
            scope_id=self.scope_id,
            ttl_seconds=ttl_seconds
        )

        # Atualizar cache local
        cache_key = f"{self.scope}:{self.scope_id}:{key}"
        self._cache[cache_key] = value

    async def delete(self, key: str) -> bool:
        """Remove valor do datastore"""
        from app.models.datastore import WorkflowDatastore
        result = WorkflowDatastore.delete_value(
            organization_id=self.organization_id,
            key=key,
            scope=self.scope,
            scope_id=self.scope_id
        )

        # Limpar cache local
        cache_key = f"{self.scope}:{self.scope_id}:{key}"
        self._cache.pop(cache_key, None)

        return result


@dataclass
class ExecutionContext:
    """
    Objeto de contexto padronizado para execução ($).

    Similar ao $ do Automatisch, fornece acesso a:
    - Autenticação da conexão
    - Metadados do app, flow, step
    - HTTP Client configurado
    - Output do trigger e action
    - Storage persistente

    Exemplo de uso em uma action:
        async def run(self, $: ExecutionContext) -> ActionResult:
            # Acessar parâmetros (já com variáveis substituídas)
            channel = $.step.parameters.get('channel')

            # Fazer requisição HTTP (já autenticada)
            response = await $.http.post('/messages', json={...})

            # Definir output para próximos steps
            $.set_action_item(response)

            return ActionResult(raw=response, data={'id': response['id']})
    """

    # Contextos
    auth: AuthContext
    app: AppContext
    flow: FlowContext
    step: StepContext
    execution: ExecutionMetadata

    # HTTP Client (configurado com auth)
    http: httpx.AsyncClient

    # Outputs
    trigger_output: TriggerOutput
    action_output: ActionOutput

    # Storage
    datastore: Datastore

    # Helpers
    webhook_url: Optional[str] = None

    # Internal: steps anteriores para referência
    _previous_steps: List[Any] = field(default_factory=list)

    def set_action_item(self, item: Any):
        """Define output para próximos steps"""
        self.action_output.data = item

    def push_trigger_item(self, item: Any):
        """Adiciona item ao trigger output"""
        self.trigger_output.push(item)

    def exit(self, reason: str = None):
        """Encerra execução antecipadamente"""
        self.execution.exit(reason)

    def get_previous_step_output(self, step_id: str) -> Optional[Dict[str, Any]]:
        """Obtém output de um step anterior"""
        for step in self._previous_steps:
            if str(step.id) == step_id or getattr(step, 'step_id', None) == step_id:
                return step.data_out
        return None


# =============================================================================
# BASE APP
# =============================================================================

class BaseApp(ABC):
    """
    Classe base abstrata para todos os apps.

    Cada app deve implementar as propriedades name, key e icon_url,
    e opcionalmente sobrescrever os métodos para auth, actions, triggers, etc.

    Exemplo de implementação:
        class HubSpotApp(BaseApp):
            @property
            def name(self) -> str:
                return 'HubSpot'

            @property
            def key(self) -> str:
                return 'hubspot'

            @property
            def icon_url(self) -> str:
                return 'https://example.com/hubspot.svg'

            def get_auth_config(self) -> AuthConfig:
                return AuthConfig(
                    auth_type=AuthType.OAUTH2,
                    oauth2_auth_url='https://app.hubspot.com/oauth/authorize',
                    ...
                )
    """

    def __init__(self):
        self._actions: Dict[str, ActionDefinition] = {}
        self._triggers: Dict[str, TriggerDefinition] = {}
        self._dynamic_data: Dict[str, DynamicDataDefinition] = {}
        self._dynamic_fields: Dict[str, DynamicFieldsDefinition] = {}
        self._before_request_hooks: List[Callable] = []
        self._after_request_hooks: List[Callable] = []
        self._setup()

    @property
    @abstractmethod
    def name(self) -> str:
        """Nome de exibição do app (ex: 'HubSpot')"""
        pass

    @property
    @abstractmethod
    def key(self) -> str:
        """Chave única do app (ex: 'hubspot')"""
        pass

    @property
    @abstractmethod
    def icon_url(self) -> str:
        """URL do ícone do app"""
        pass

    @property
    def description(self) -> str:
        """Descrição do app"""
        return ''

    @property
    def version(self) -> str:
        """Versão do app"""
        return '1.0.0'

    @property
    def base_url(self) -> Optional[str]:
        """URL base para chamadas de API (opcional)"""
        return None

    @property
    def documentation_url(self) -> Optional[str]:
        """URL para documentação do app"""
        return None

    def _setup(self):
        """
        Método chamado durante inicialização.
        Subclasses podem sobrescrever para registrar actions, triggers, etc.
        """
        pass

    def get_auth_config(self) -> AuthConfig:
        """
        Retorna configuração de autenticação.
        Subclasses devem sobrescrever se precisam de autenticação.
        """
        return AuthConfig(auth_type=AuthType.NONE)

    def register_action(self, action: ActionDefinition):
        """Registra uma action no app"""
        self._actions[action.key] = action

    def register_trigger(self, trigger: TriggerDefinition):
        """Registra um trigger no app"""
        self._triggers[trigger.key] = trigger

    def register_dynamic_data(self, data: DynamicDataDefinition):
        """Registra dados dinâmicos no app"""
        self._dynamic_data[data.key] = data

    def register_dynamic_fields(self, definition: DynamicFieldsDefinition):
        """Registra definição de campos dinâmicos no app"""
        self._dynamic_fields[definition.key] = definition

    def get_dynamic_fields_definition(self, key: str) -> Optional[DynamicFieldsDefinition]:
        """Retorna definição de campos dinâmicos pelo key"""
        return self._dynamic_fields.get(key)

    def get_dynamic_fields_list(self) -> List[DynamicFieldsDefinition]:
        """Retorna lista de definições de campos dinâmicos disponíveis"""
        return list(self._dynamic_fields.values())

    async def fetch_dynamic_fields(
        self,
        key: str,
        connection_id: str = None,
        context: Dict[str, Any] = None,
    ) -> List[Dict[str, Any]]:
        """
        Busca campos dinâmicos.

        Args:
            key: Chave da definição de campos dinâmicos
            connection_id: ID da conexão (para autenticação)
            context: Valores atuais dos campos que esta definição depende

        Returns:
            Lista de arguments no formato [{'key': '', 'label': '', ...}]
        """
        definition = self.get_dynamic_fields_definition(key)
        if not definition:
            return []

        http_client = await self.create_http_client(connection_id)
        try:
            fields = await definition.get_fields(http_client, context or {})
            return [f.to_dict() for f in fields]
        finally:
            if http_client:
                await http_client.aclose()

    def add_before_request_hook(self, hook: Callable):
        """Adiciona hook executado antes de cada requisição"""
        self._before_request_hooks.append(hook)

    def add_after_request_hook(self, hook: Callable):
        """Adiciona hook executado após cada requisição"""
        self._after_request_hooks.append(hook)

    def get_actions(self) -> List[ActionDefinition]:
        """Retorna lista de actions disponíveis"""
        return list(self._actions.values())

    def get_action(self, key: str) -> Optional[ActionDefinition]:
        """Retorna uma action específica pelo key"""
        return self._actions.get(key)

    def get_triggers(self) -> List[TriggerDefinition]:
        """Retorna lista de triggers disponíveis"""
        return list(self._triggers.values())

    def get_trigger(self, key: str) -> Optional[TriggerDefinition]:
        """Retorna um trigger específico pelo key"""
        return self._triggers.get(key)

    def get_dynamic_data_list(self) -> List[DynamicDataDefinition]:
        """Retorna lista de dados dinâmicos disponíveis"""
        return list(self._dynamic_data.values())

    def get_dynamic_data(self, key: str) -> Optional[DynamicDataDefinition]:
        """Retorna dados dinâmicos específicos pelo key"""
        return self._dynamic_data.get(key)

    async def fetch_dynamic_data(
        self,
        key: str,
        connection_id: str = None,
        params: Dict[str, Any] = None,
    ) -> List[Dict[str, Any]]:
        """
        Busca dados dinâmicos.

        Args:
            key: Chave do dynamic data
            connection_id: ID da conexão (para autenticação)
            params: Parâmetros adicionais

        Returns:
            Lista de items no formato [{'label': '', 'value': ''}, ...]
        """
        data_def = self.get_dynamic_data(key)
        if not data_def:
            return []

        http_client = await self.create_http_client(connection_id)
        try:
            return await data_def.handler(http_client, params or {})
        finally:
            if http_client:
                await http_client.aclose()

    async def execute_action(
        self,
        action_key: str,
        connection_id: str = None,
        parameters: Dict[str, Any] = None,
        context: Any = None,
    ) -> Dict[str, Any]:
        """
        Executa uma action do app.

        Args:
            action_key: Chave da action
            connection_id: ID da conexão (para autenticação)
            parameters: Parâmetros da action
            context: GlobalVariable context ($)

        Returns:
            Resultado da action
        """
        action = self.get_action(action_key)
        if not action:
            raise ValueError(f"Action '{action_key}' not found in app '{self.key}'")

        http_client = None
        if action.requires_connection:
            http_client = await self.create_http_client(connection_id)

        try:
            return await action.handler(
                http_client=http_client,
                parameters=parameters or {},
                context=context,
            )
        finally:
            if http_client:
                await http_client.aclose()

    async def execute_trigger(
        self,
        trigger_key: str,
        connection_id: str = None,
        trigger_data: Dict[str, Any] = None,
        context: Any = None,
    ) -> Dict[str, Any]:
        """
        Executa um trigger do app.

        Args:
            trigger_key: Chave do trigger
            connection_id: ID da conexão
            trigger_data: Dados do trigger (webhook payload, etc)
            context: GlobalVariable context ($)

        Returns:
            Dados processados do trigger
        """
        trigger = self.get_trigger(trigger_key)
        if not trigger:
            raise ValueError(f"Trigger '{trigger_key}' not found in app '{self.key}'")

        http_client = await self.create_http_client(connection_id)
        try:
            return await trigger.handler(
                http_client=http_client,
                trigger_data=trigger_data or {},
                context=context,
            )
        finally:
            if http_client:
                await http_client.aclose()

    async def create_http_client(
        self,
        connection_id: str = None,
        timeout: float = 30.0,
    ) -> Optional[httpx.AsyncClient]:
        """
        Cria cliente HTTP configurado com autenticação.

        Args:
            connection_id: ID da conexão no banco
            timeout: Timeout em segundos

        Returns:
            httpx.AsyncClient configurado ou None se não precisar de HTTP
        """
        headers = {}
        auth = None
        credentials = None

        if connection_id:
            # Buscar credenciais do banco
            credentials = await self._get_connection_credentials(connection_id)
            if credentials:
                auth_config = self.get_auth_config()

                if auth_config.auth_type == AuthType.BEARER:
                    access_token = credentials.get('access_token')
                    if access_token:
                        headers['Authorization'] = f'Bearer {access_token}'

                elif auth_config.auth_type == AuthType.API_KEY:
                    api_key = credentials.get('api_key')
                    if api_key and auth_config.api_key_header:
                        headers[auth_config.api_key_header] = api_key

                elif auth_config.auth_type == AuthType.OAUTH2:
                    access_token = credentials.get('access_token')
                    if access_token:
                        headers['Authorization'] = f'Bearer {access_token}'

                elif auth_config.auth_type == AuthType.BASIC:
                    username = credentials.get('username')
                    password = credentials.get('password')
                    if username and password:
                        auth = httpx.BasicAuth(username, password)

        # Preparar event hooks se hooks estão registrados
        event_hooks = {}
        if self._before_request_hooks or self._after_request_hooks:
            # Armazenar contexto para os hooks
            hook_context = {
                'credentials': credentials,
                'connection_id': connection_id,
                'app_key': self.key,
            }

            if self._before_request_hooks:
                async def request_hook(request):
                    for hook in self._before_request_hooks:
                        await hook(request, hook_context)
                event_hooks['request'] = [request_hook]

            if self._after_request_hooks:
                async def response_hook(response):
                    for hook in self._after_request_hooks:
                        await hook(response, hook_context)
                event_hooks['response'] = [response_hook]

        client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            auth=auth,
            timeout=timeout,
            event_hooks=event_hooks if event_hooks else None,
        )

        return client

    async def _get_connection_credentials(
        self,
        connection_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Busca credenciais de uma conexão do banco.

        Args:
            connection_id: ID da DataSourceConnection

        Returns:
            Dict com credenciais ou None
        """
        # Import aqui para evitar circular imports
        from app.models import DataSourceConnection

        connection = DataSourceConnection.query.get(connection_id)
        if connection:
            return connection.get_credentials()
        return None

    async def test_connection(
        self,
        connection_id: str = None,
        credentials: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Testa se a conexão está funcionando.

        Args:
            connection_id: ID da conexão existente
            credentials: Credenciais para testar (sem salvar)

        Returns:
            {'success': bool, 'message': str}
        """
        # Implementação padrão - subclasses devem sobrescrever
        return {'success': True, 'message': 'Connection test not implemented'}

    def to_dict(self) -> Dict[str, Any]:
        """Converte app para dicionário"""
        return {
            'key': self.key,
            'name': self.name,
            'description': self.description,
            'version': self.version,
            'icon_url': self.icon_url,
            'documentation_url': self.documentation_url,
            'base_url': self.base_url,
            'auth_config': self.get_auth_config().to_dict(),
            'actions': [a.to_dict() for a in self.get_actions()],
            'triggers': [t.to_dict() for t in self.get_triggers()],
            'dynamic_data': [d.to_dict() for d in self.get_dynamic_data_list()],
        }


class BaseAction:
    """
    Classe base para actions reutilizáveis.

    Facilita a criação de actions como classes ao invés de funções.

    Exemplo NOVO (com ExecutionContext):
        class CreateContactAction(BaseAction):
            key = 'create-contact'
            name = 'Create Contact'
            description = 'Creates a new contact'

            arguments = [
                ActionArgument(
                    key='email',
                    label='Email',
                    type=ArgumentType.STRING,
                    required=True
                ),
                ActionArgument(
                    key='name',
                    label='Name',
                    type=ArgumentType.STRING
                )
            ]

            async def run(self, $: ExecutionContext) -> ActionResult:
                response = await $.http.post('/contacts', json=$.step.parameters)
                return ActionResult(
                    raw=response.json(),
                    data={'id': response.json()['id']}
                )

    Exemplo LEGADO (ainda suportado):
        class CreateContactAction(BaseAction):
            async def run(self, http_client, parameters, context):
                response = await http_client.post('/contacts', json=parameters)
                return response.json()
    """

    key: str = ''
    name: str = ''
    description: str = ''
    requires_connection: bool = True

    # NOVO: Schema rico de arguments
    arguments: List[ActionArgument] = []

    # Legado: mantido para compatibilidade
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None

    async def run(
        self,
        context_or_http: Union[ExecutionContext, httpx.AsyncClient],
        parameters: Dict[str, Any] = None,
        legacy_context: Any = None,
    ) -> Union[ActionResult, Dict[str, Any]]:
        """
        Executa a action.

        Suporta duas assinaturas:
        - NOVO: run($: ExecutionContext) -> ActionResult
        - LEGADO: run(http_client, parameters, context) -> Dict

        Args:
            context_or_http: ExecutionContext ($) ou httpx.AsyncClient (legado)
            parameters: Parâmetros (apenas legado)
            legacy_context: Contexto antigo (apenas legado)

        Returns:
            ActionResult ou Dict (legado)
        """
        raise NotImplementedError("Subclasses must implement run()")

    def to_definition(self) -> ActionDefinition:
        """Converte para ActionDefinition"""
        return ActionDefinition(
            key=self.key,
            name=self.name,
            description=self.description,
            handler=self.run,
            arguments=self.arguments if self.arguments else [],
            input_schema=self.input_schema,
            output_schema=self.output_schema,
            requires_connection=self.requires_connection,
        )


class BaseTrigger:
    """
    Classe base para triggers reutilizáveis.

    Similar a BaseAction, mas para triggers.

    Exemplo:
        class NewDealTrigger(BaseTrigger):
            key = 'new-deal'
            name = 'New Deal Created'
            trigger_type = 'webhook'

            arguments = [
                ActionArgument(
                    key='deal_pipeline',
                    label='Pipeline',
                    type=ArgumentType.DROPDOWN,
                    source=DynamicDataSource(key='listPipelines')
                )
            ]

            async def run(self, $: ExecutionContext) -> ActionResult:
                # Processar dados do webhook
                deal = $.step.parameters.get('trigger_data', {})
                return ActionResult(
                    raw=deal,
                    data={'id': deal.get('id'), 'name': deal.get('name')}
                )
    """

    key: str = ''
    name: str = ''
    description: str = ''
    trigger_type: str = 'webhook'  # 'webhook', 'polling', 'subscription'

    # NOVO: Schema rico de arguments
    arguments: List[ActionArgument] = []

    # Legado: mantido para compatibilidade
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None

    async def run(
        self,
        context_or_http: Union[ExecutionContext, httpx.AsyncClient],
        trigger_data: Dict[str, Any] = None,
        legacy_context: Any = None,
    ) -> Union[ActionResult, Dict[str, Any]]:
        """
        Processa dados do trigger.

        Suporta duas assinaturas:
        - NOVO: run($: ExecutionContext) -> ActionResult
        - LEGADO: run(http_client, trigger_data, context) -> Dict

        Args:
            context_or_http: ExecutionContext ($) ou httpx.AsyncClient
            trigger_data: Dados do trigger (apenas legado)
            legacy_context: Contexto antigo (apenas legado)

        Returns:
            ActionResult ou Dict com dados processados
        """
        raise NotImplementedError("Subclasses must implement run()")

    def to_definition(self) -> TriggerDefinition:
        """Converte para TriggerDefinition"""
        return TriggerDefinition(
            key=self.key,
            name=self.name,
            description=self.description,
            handler=self.run,
            trigger_type=self.trigger_type,
            arguments=self.arguments if self.arguments else [],
            input_schema=self.input_schema,
            output_schema=self.output_schema,
        )
