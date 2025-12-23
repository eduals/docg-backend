# Arquitetura de Execução de Workflows - DocG

> **Versão:** 6.0
> **Data:** 22 de Dezembro de 2025
> **Baseado em:** Automatisch Pattern

---

## O Que É Isso?

DocG executa **workflows** = sequências de passos (nodes) que processam dados, geram documentos, coletam assinaturas e enviam notificações.

Este documento explica **como a engine funciona por baixo dos panos**.

---

## Visão Geral da Arquitetura

```
┌─────────────────────────────────────────────────────────────────────┐
│                         ENTRADAS                                    │
│  HubSpot Action  │  Webhook  │  Google Forms  │  API Manual         │
└────────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         ENGINE                                       │
│                                                                      │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐     │
│   │   Engine     │───▶│  iterate_    │───▶│  process_step    │     │
│   │   .run()     │    │  steps()     │    │  (action/trigger)│     │
│   └──────────────┘    └──────────────┘    └──────────────────┘     │
│         │                    │                      │               │
│         ▼                    ▼                      ▼               │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐     │
│   │  Concurrent  │    │  Branching   │    │ ExecutionContext │     │
│   │  Lock Check  │    │  Support     │    │      ($)         │     │
│   └──────────────┘    └──────────────┘    └──────────────────┘     │
│         │                    │                      │               │
│         ▼                    ▼                      ▼               │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐     │
│   │  Validation  │    │  compute_    │    │   Datastore      │     │
│   │  (Arguments) │    │  parameters  │    │   (Persistente)  │     │
│   └──────────────┘    └──────────────┘    └──────────────────┘     │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    APPS MODULARES                                    │
│                                                                      │
│   hubspot  │  google-docs  │  clicksign  │  gmail  │  ai  │ ...    │
│                                                                      │
│   (with beforeRequest/afterRequest hooks)                           │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Componentes Principais

### 1. Engine (`app/engine/engine.py`)

Ponto de entrada. Decide se executa via Temporal ou síncrono.

```python
Engine.run(
    workflow_id,
    trigger_data,
    test_run=False,
    until_step=None,      # Para antes de step específico
    skip_steps=None,      # Lista de steps a pular
    mock_data=None        # Mock outputs por step
)
```

- **Temporal habilitado**: Inicia execução assíncrona (background)
- **test_run=True ou sem Temporal**: Executa síncronamente
- **Concurrent Check**: Verifica se workflow já está rodando

### 2. ExecutionContext - O Objeto `$`

É o **contexto padronizado** passado para toda action/trigger. Similar ao `$` do Automatisch.

**Localização:** `app/apps/base.py`

```python
@dataclass
class ExecutionContext:
    auth: AuthContext       # Credenciais da conexão
    app: AppContext         # Metadados do app
    flow: FlowContext       # ID e nome do workflow
    step: StepContext       # Step atual + parâmetros JÁ COMPUTADOS
    execution: ExecutionMetadata  # ID execução, test_run
    http: httpx.AsyncClient # Cliente HTTP já autenticado (com hooks)
    trigger_output: TriggerOutput
    action_output: ActionOutput
    datastore: Datastore    # Storage PERSISTENTE no PostgreSQL
```

**Uso em uma action:**

```python
async def run(self, $: ExecutionContext) -> ActionResult:
    # Parâmetros já vêm com {{step.x.y}} substituídos
    channel = $.step.parameters.get('channel')

    # HTTP já vem com auth configurado + hooks
    response = await $.http.post('/messages', json={...})

    # Datastore persistente (PostgreSQL)
    await $.datastore.set('last_sync', datetime.now().isoformat())
    cached = await $.datastore.get('last_sync')

    return ActionResult(raw=response, data={'id': response['id']})
```

### 3. Validação de Parâmetros (`app/engine/validate_parameters.py`)

Valida parâmetros contra schema de ActionArguments **antes de executar**.

```python
from app.engine.validate_parameters import validate_and_raise, ValidationError

# Valida: required, tipos, min/max, patterns
errors = validate_parameters(params, action.arguments)
# {'email': ["'Email' is required"], 'age': ["'Age' must be a number"]}

# Ou levanta exception
try:
    validate_and_raise(params, action.arguments)
except ValidationError as e:
    print(e.errors)  # Dict com erros por campo
```

### 4. compute_parameters (`app/engine/compute_parameters.py`)

Substitui variáveis `{{step.x.y}}` antes de executar cada step.

| Formato | Exemplo | Descrição |
|---------|---------|-----------|
| `{{step.{id}.{path}}}` | `{{step.abc.email}}` | Valor de step anterior |
| `{{trigger.{path}}}` | `{{trigger.deal.name}}` | Valor do trigger |
| `{{flow.{path}}}` | `{{flow.id}}` | Metadados do workflow |
| `{{execution.{path}}}` | `{{execution.id}}` | Metadados da execução |
| `{{env.{VAR}}}` | `{{env.API_KEY}}` | Variável de ambiente |
| `{{now}}` | - | Data/hora atual ISO |
| `{{uuid}}` | - | UUID aleatório |

### 5. ActionResult

Output padronizado de todas as actions.

```python
@dataclass
class ActionResult:
    raw: Any              # Resposta bruta da API
    data: Dict[str, Any]  # Campos mapeados para fácil acesso
    metadata: dict        # Info extra (pagination, etc)
```

### 6. ActionArgument (com validação)

Schema rico para campos de input. Define como a UI renderiza e **valida** cada campo.

```python
@dataclass
class ActionArgument:
    key: str                    # 'channel'
    label: str                  # 'Canal'
    type: ArgumentType          # DROPDOWN, STRING, MULTILINE, etc
    required: bool = False      # Validado em runtime
    variables: bool = True      # Aceita {{step.x.y}}
    source: DynamicDataSource   # Para dropdowns dinâmicos
    depends_on: str             # Campo que controla visibilidade
    additional_fields: DynamicFieldsSource  # Campos condicionais

    # Validação
    min_length: int = None
    max_length: int = None
    min_value: float = None
    max_value: float = None
    pattern: str = None         # Regex
```

---

## Fluxo de Execução

### Passo a Passo

```
1. ENTRADA
   └─ API/Webhook/HubSpot chama Engine.run(workflow_id, trigger_data)

2. CONCURRENT CHECK (Optimistic Locking)
   └─ WorkflowExecution.check_concurrent_execution(workflow_id)
       └─ Se já running → ConcurrentExecutionError

3. ENGINE DECIDE
   ├─ Temporal habilitado? → run_in_background() → retorna imediatamente
   └─ Não? → iterate_steps() → executa síncrono

4. ITERATE STEPS (while loop com branching)
   └─ current_node = get_first_action_node()
   └─ while current_node:
       ├─ until_step? → para antes
       ├─ skip_steps? → pula step
       ├─ mock_data? → usa mock output
       ├─ validate_parameters() → valida required, tipos
       ├─ compute_parameters() → substitui {{variáveis}}
       ├─ build_execution_context() → monta o objeto $
       ├─ process_step() → executa action/trigger
       └─ current_node = get_next_node() → branching ou sequencial

5. PROCESS STEP
   ├─ Trigger? → process_trigger_step()
   └─ Action? → process_action_step()
       ├─ validate_and_raise() → ValidationError se inválido
       └─ app.execute_action(action_key, $)
           └─ action.run($) → retorna ActionResult

6. APÓS CADA STEP
   ├─ Salva ExecutionStep no banco (data_in, data_out)
   └─ Adiciona output a previous_steps (para compute_parameters)

7. BRANCHING (se node.structural_type == 'branch')
   └─ Avalia branch_conditions com operadores
   └─ get_next_node_id() retorna próximo node

8. PAUSAS (approval/signature)
   ├─ Cria WorkflowApproval ou SignatureRequest
   ├─ Marca execution como 'paused'
   └─ Aguarda signal para retomar

9. FIM
   └─ Atualiza status para 'completed' ou 'failed'
```

---

## Branching (Caminhos Condicionais)

Nodes podem ter `structural_type = 'branch'` para criar caminhos condicionais.

**Implementado em:**
- `app/models/workflow.py` - `WorkflowNode.get_next_node_id()`
- `app/engine/flow/context.py` - `get_next_node()`
- `app/temporal/workflows/docg_workflow.py` - `_get_next_node()`

```python
structural_type = 'branch'  # 'single', 'branch', 'paths'
branch_conditions = [
    {
        "name": "Deal > 10k",
        "conditions": {
            "type": "and",  # ou "or"
            "rules": [
                {"field": "{{step.trigger.amount}}", "operator": ">", "value": 10000}
            ]
        },
        "next_node_id": "uuid-high-value"
    },
    {
        "name": "Default",
        "conditions": None,  # null = caminho default
        "next_node_id": "uuid-default"
    }
]
```

**Operadores suportados:**

| Operador | Descrição |
|----------|-----------|
| `==` | Igual |
| `!=` | Diferente |
| `>`, `<`, `>=`, `<=` | Comparação numérica |
| `contains` | String contém |
| `not_contains` | String não contém |
| `starts_with` | String começa com |
| `ends_with` | String termina com |
| `is_empty` | Valor vazio/nulo |
| `is_not_empty` | Valor preenchido |

---

## Datastore Persistente

Storage key-value persistente no PostgreSQL com suporte a TTL.

**Model:** `app/models/datastore.py`
**Classe:** `app/apps/base.py` - `Datastore`

```python
@dataclass
class Datastore:
    organization_id: str
    scope: str = 'organization'  # 'organization', 'workflow', 'execution'
    scope_id: str = None

    async def get(self, key: str) -> Any
    async def set(self, key: str, value: Any, ttl_seconds: int = None)
    async def delete(self, key: str) -> bool
```

**Escopos:**
- `organization`: Compartilhado por toda organização
- `workflow`: Específico para um workflow
- `execution`: Específico para uma execução

**Uso:**
```python
# Na action
await $.datastore.set('counter', 42)
await $.datastore.set('temp', 'value', ttl_seconds=3600)  # Expira em 1h

count = await $.datastore.get('counter')
await $.datastore.delete('counter')
```

---

## Middleware Auth (beforeRequest/afterRequest)

Apps podem registrar hooks que são executados antes/depois de cada request HTTP.

**Implementado em:** `app/apps/base.py` - `create_http_client()`

```python
class MyApp(BaseApp):
    def _setup(self):
        self.add_before_request_hook(self._add_custom_header)
        self.add_after_request_hook(self._log_response)

    async def _add_custom_header(self, request, context):
        request.headers['X-Custom'] = 'value'

    async def _log_response(self, response, context):
        logger.info(f"Response: {response.status_code}")
```

**Hook Context:**
```python
{
    'credentials': {...},      # Credenciais da conexão
    'connection_id': 'uuid',   # ID da conexão
    'app_key': 'hubspot'       # Key do app
}
```

---

## Test Run Granular

Permite controle fino sobre execução de testes.

**Implementado em:** `app/engine/engine.py`, `app/engine/steps/iterate.py`

```python
# Parar antes de step específico
await Engine.run(
    workflow_id='...',
    test_run=True,
    until_step='step-uuid-3'  # Para ANTES deste step
)

# Pular steps
await Engine.run(
    workflow_id='...',
    test_run=True,
    skip_steps=['step-uuid-2', 'step-uuid-4']  # Pula estes
)

# Mock data para steps
await Engine.run(
    workflow_id='...',
    test_run=True,
    mock_data={
        'step-uuid-2': {'id': 'mock-123', 'status': 'success'}
    }
)
```

---

## Optimistic Locking

Previne execuções concorrentes do mesmo workflow.

**Implementado em:** `app/models/execution.py`, `app/engine/engine.py`

```python
# Modelo
class WorkflowExecution(db.Model):
    version = db.Column(db.Integer, default=1)

    @classmethod
    def check_concurrent_execution(cls, workflow_id):
        running = cls.query.filter_by(
            workflow_id=workflow_id,
            status='running'
        ).first()
        if running:
            raise ConcurrentExecutionError(workflow_id, str(running.id))

# Exception
class ConcurrentExecutionError(Exception):
    def __init__(self, workflow_id, execution_id=None):
        self.workflow_id = workflow_id
        self.execution_id = execution_id
```

---

## Dynamic Fields

Campos condicionais que aparecem baseado em seleções anteriores.

**Implementado em:**
- `app/apps/base.py` - `DynamicFieldsDefinition`
- `app/controllers/api/v1/apps/dynamic_fields_controller.py`

```python
# Definição
class HubSpotObjectFields(DynamicFieldsDefinition):
    key = 'objectFields'
    depends_on = ['object_type']

    async def get_fields(self, http_client, context):
        object_type = context.get('object_type')
        # Buscar propriedades do objeto
        response = await http_client.get(f'/properties/{object_type}')
        return [
            ActionArgument(key=p['name'], label=p['label'], ...)
            for p in response.json()['results']
        ]

# Registro no App
class HubSpotApp(BaseApp):
    def _setup(self):
        self.register_dynamic_fields(HubSpotObjectFields())

# Endpoint
GET /api/v1/apps/{app_key}/dynamic-fields/{definition_key}?object_type=contact
```

---

## Arquivos Chave

| Arquivo | Função |
|---------|--------|
| `app/engine/engine.py` | Engine principal + concurrent check |
| `app/engine/validate_parameters.py` | **NOVO** - Validação de arguments |
| `app/engine/compute_parameters.py` | Substituição de variáveis |
| `app/engine/steps/iterate.py` | Loop com branching + test run granular |
| `app/engine/flow/context.py` | `get_next_node()` com branching |
| `app/engine/action/process.py` | Processamento + validação |
| `app/apps/base.py` | BaseApp, Datastore, DynamicFieldsDefinition, hooks |
| `app/models/workflow.py` | `get_next_node_id()` branching |
| `app/models/execution.py` | ConcurrentExecutionError, version |
| `app/models/datastore.py` | **NOVO** - WorkflowDatastore model |
| `app/controllers/api/v1/apps/` | **NOVO** - Dynamic fields controller |
| `app/temporal/workflows/docg_workflow.py` | Branching no Temporal |

---

## Testes

```bash
# Rodar todos os testes da engine
pytest tests/engine/ -v

# Por fase
pytest tests/engine/test_branching.py -v           # Branching
pytest tests/engine/test_validate_parameters.py -v # Validação
pytest tests/engine/test_datastore.py -v           # Datastore
pytest tests/engine/test_middleware_auth.py -v     # Hooks
pytest tests/engine/test_engine.py -v              # Test Run + Locking
pytest tests/engine/test_dynamic_fields.py -v      # Dynamic Fields
```

---

## Próximos Passos

### Melhorias Pendentes

1. **Múltiplos Caminhos Paralelos (`paths`)**
   - Suportar execução paralela de branches

2. **Logs Estruturados**
   - Adicionar tracing por execution_id
   - Métricas de duração por step

3. **WebSockets**
   - Updates em tempo real de execuções

4. **Cache de IA**
   - Evitar chamadas duplicadas

5. **Documentação de Apps**
   - Gerar docs automáticos dos arguments
   - Exemplos de uso para cada action

---

**Última atualização:** 22 de Dezembro de 2025
