"""
Global Variable System ($) - Contexto compartilhado entre steps.

Similar ao sistema de Global Variable ($) do Automatisch, este módulo
fornece o objeto de contexto que é passado para cada step durante a execução.

O objeto $ contém:
- $.auth: Dados de autenticação da conexão atual
- $.flow: Informações do workflow
- $.step: Step atual com parâmetros
- $.execution: Execução atual
- $.http: Cliente HTTP configurado com auth (quando aplicável)
- $.actionOutput: Output do último action step
- $.triggerOutput: Output do trigger step
- $.previousSteps: Outputs de todos os steps anteriores (para computeParameters)
- $.datastore: Armazenamento de dados do workflow (opcional)
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
import httpx


@dataclass
class AuthContext:
    """Contexto de autenticação para conexões"""
    connection_id: Optional[str] = None
    auth_type: Optional[str] = None  # 'oauth2', 'api_key', 'basic', etc
    credentials: Dict[str, Any] = field(default_factory=dict)
    # OAuth2 specific
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_type: Optional[str] = None
    expires_at: Optional[str] = None
    # API Key specific
    api_key: Optional[str] = None
    api_key_header: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'connection_id': self.connection_id,
            'auth_type': self.auth_type,
            'credentials': self.credentials,
            'access_token': self.access_token,
            'refresh_token': self.refresh_token,
            'token_type': self.token_type,
            'expires_at': self.expires_at,
            'api_key': self.api_key,
            'api_key_header': self.api_key_header,
        }


@dataclass
class FlowContext:
    """Contexto do workflow"""
    workflow_id: str
    workflow_name: str
    organization_id: str
    status: str
    trigger_type: Optional[str] = None
    trigger_config: Optional[Dict[str, Any]] = None
    nodes: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'workflow_id': self.workflow_id,
            'workflow_name': self.workflow_name,
            'organization_id': self.organization_id,
            'status': self.status,
            'trigger_type': self.trigger_type,
            'trigger_config': self.trigger_config,
            'nodes': self.nodes,
        }


@dataclass
class StepContext:
    """Contexto do step atual"""
    step_id: str
    step_type: str
    position: int
    app_key: Optional[str] = None
    action_key: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    config: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'step_id': self.step_id,
            'step_type': self.step_type,
            'position': self.position,
            'app_key': self.app_key,
            'action_key': self.action_key,
            'parameters': self.parameters,
            'config': self.config,
        }


@dataclass
class ExecutionContext:
    """Contexto da execução atual"""
    execution_id: str
    started_at: Optional[str] = None
    status: str = 'running'
    trigger_data: Dict[str, Any] = field(default_factory=dict)
    test_run: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            'execution_id': self.execution_id,
            'started_at': self.started_at,
            'status': self.status,
            'trigger_data': self.trigger_data,
            'test_run': self.test_run,
        }


@dataclass
class PreviousStepOutput:
    """Output de um step anterior (para computeParameters)"""
    step_id: str
    step_type: str
    position: int
    data_out: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'step_id': self.step_id,
            'step_type': self.step_type,
            'position': self.position,
            'data_out': self.data_out,
        }


class GlobalVariable:
    """
    Objeto de contexto global ($) passado para cada step.

    Similar ao $ do Automatisch, fornece acesso a:
    - Autenticação
    - Informações do workflow
    - Step atual
    - Execução
    - Outputs anteriores
    - Cliente HTTP configurado

    Exemplo de uso em uma action:
        def run(self, $: GlobalVariable):
            # Acessar dados do trigger
            contact_id = $.triggerOutput.get('contact', {}).get('id')

            # Fazer requisição autenticada
            response = $.http.get(f'/contacts/{contact_id}')

            # Retornar output para próximos steps
            return {'contact_data': response.json()}
    """

    def __init__(
        self,
        auth: Optional[AuthContext] = None,
        flow: Optional[FlowContext] = None,
        step: Optional[StepContext] = None,
        execution: Optional[ExecutionContext] = None,
        trigger_output: Optional[Dict[str, Any]] = None,
        action_output: Optional[Dict[str, Any]] = None,
        previous_steps: Optional[List[PreviousStepOutput]] = None,
        datastore: Optional[Dict[str, Any]] = None,
        http_client: Optional[httpx.Client] = None,
    ):
        self._auth = auth or AuthContext()
        self._flow = flow
        self._step = step
        self._execution = execution
        self._trigger_output = trigger_output or {}
        self._action_output = action_output or {}
        self._previous_steps = previous_steps or []
        self._datastore = datastore or {}
        self._http_client = http_client

    @property
    def auth(self) -> AuthContext:
        """Dados de autenticação da conexão atual"""
        return self._auth

    @property
    def flow(self) -> Optional[FlowContext]:
        """Informações do workflow"""
        return self._flow

    @property
    def step(self) -> Optional[StepContext]:
        """Step atual com parâmetros"""
        return self._step

    @property
    def execution(self) -> Optional[ExecutionContext]:
        """Execução atual"""
        return self._execution

    @property
    def triggerOutput(self) -> Dict[str, Any]:
        """Output do trigger step (dados da fonte)"""
        return self._trigger_output

    @property
    def actionOutput(self) -> Dict[str, Any]:
        """Output do último action step"""
        return self._action_output

    @property
    def previousSteps(self) -> List[PreviousStepOutput]:
        """Lista de outputs de steps anteriores"""
        return self._previous_steps

    @property
    def datastore(self) -> Dict[str, Any]:
        """Armazenamento de dados do workflow"""
        return self._datastore

    @property
    def http(self) -> Optional[httpx.Client]:
        """Cliente HTTP configurado com autenticação"""
        return self._http_client

    def get_step_output(self, step_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtém o output de um step específico pelo ID.

        Args:
            step_id: ID do step

        Returns:
            data_out do step ou None se não encontrado
        """
        for prev_step in self._previous_steps:
            if prev_step.step_id == step_id:
                return prev_step.data_out
        return None

    def get_step_output_by_position(self, position: int) -> Optional[Dict[str, Any]]:
        """
        Obtém o output de um step específico pela posição.

        Args:
            position: Posição do step no workflow

        Returns:
            data_out do step ou None se não encontrado
        """
        for prev_step in self._previous_steps:
            if prev_step.position == position:
                return prev_step.data_out
        return None

    def get_value(self, key_path: str) -> Any:
        """
        Obtém um valor usando key path.

        Suporta:
        - triggerOutput.field.subfield
        - actionOutput.field.subfield
        - step.{stepId}.field.subfield
        - flow.workflow_id
        - execution.execution_id

        Args:
            key_path: Caminho para o valor (separado por pontos)

        Returns:
            O valor encontrado ou None
        """
        parts = key_path.split('.')
        if not parts:
            return None

        root = parts[0]

        if root == 'triggerOutput':
            return self._get_nested_value(self._trigger_output, parts[1:])
        elif root == 'actionOutput':
            return self._get_nested_value(self._action_output, parts[1:])
        elif root == 'step' and len(parts) >= 3:
            step_id = parts[1]
            step_output = self.get_step_output(step_id)
            if step_output:
                return self._get_nested_value(step_output, parts[2:])
            return None
        elif root == 'flow' and self._flow:
            return self._get_nested_value(self._flow.to_dict(), parts[1:])
        elif root == 'execution' and self._execution:
            return self._get_nested_value(self._execution.to_dict(), parts[1:])
        elif root == 'auth':
            return self._get_nested_value(self._auth.to_dict(), parts[1:])
        elif root == 'datastore':
            return self._get_nested_value(self._datastore, parts[1:])

        return None

    def _get_nested_value(self, obj: Any, keys: List[str]) -> Any:
        """Obtém valor aninhado de um objeto"""
        if not keys:
            return obj

        for key in keys:
            if isinstance(obj, dict):
                obj = obj.get(key)
            elif isinstance(obj, list):
                try:
                    index = int(key)
                    obj = obj[index]
                except (ValueError, IndexError):
                    return None
            else:
                return None

            if obj is None:
                return None

        return obj

    def set_trigger_output(self, output: Dict[str, Any]):
        """Define o output do trigger"""
        self._trigger_output = output

    def set_action_output(self, output: Dict[str, Any]):
        """Define o output da última action"""
        self._action_output = output

    def add_step_output(self, step_id: str, step_type: str, position: int, data_out: Dict[str, Any]):
        """Adiciona output de um step aos anteriores"""
        self._previous_steps.append(PreviousStepOutput(
            step_id=step_id,
            step_type=step_type,
            position=position,
            data_out=data_out,
        ))

    def set_datastore(self, key: str, value: Any):
        """Define um valor no datastore"""
        self._datastore[key] = value

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário (para serialização)"""
        return {
            'auth': self._auth.to_dict() if self._auth else None,
            'flow': self._flow.to_dict() if self._flow else None,
            'step': self._step.to_dict() if self._step else None,
            'execution': self._execution.to_dict() if self._execution else None,
            'triggerOutput': self._trigger_output,
            'actionOutput': self._action_output,
            'previousSteps': [s.to_dict() for s in self._previous_steps],
            'datastore': self._datastore,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GlobalVariable':
        """Cria instância a partir de dicionário"""
        auth = None
        if data.get('auth'):
            auth = AuthContext(**data['auth'])

        flow = None
        if data.get('flow'):
            flow = FlowContext(**data['flow'])

        step = None
        if data.get('step'):
            step = StepContext(**data['step'])

        execution = None
        if data.get('execution'):
            execution = ExecutionContext(**data['execution'])

        previous_steps = []
        if data.get('previousSteps'):
            previous_steps = [PreviousStepOutput(**s) for s in data['previousSteps']]

        return cls(
            auth=auth,
            flow=flow,
            step=step,
            execution=execution,
            trigger_output=data.get('triggerOutput', {}),
            action_output=data.get('actionOutput', {}),
            previous_steps=previous_steps,
            datastore=data.get('datastore', {}),
        )


# Nota: Em Python, não é possível usar $ como identificador.
# Use GlobalVariable ou importe ExecutionContext de app.apps.base
# para o novo padrão estilo Automatisch.
