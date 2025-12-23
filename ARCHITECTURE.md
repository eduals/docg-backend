# Arquitetura DocG Backend

> **Versão:** 3.0
> **Data:** 22 de Dezembro de 2025
> **Padrão:** Automatisch-style

---

## O Que É o DocG?

Sistema de **geração automatizada de documentos** com:
- Integração com CRMs (HubSpot)
- Templates (Google Docs, Word, uploads)
- Assinatura digital (ClickSign, ZapSign)
- IA para geração de conteúdo
- Workflows visuais

---

## Stack Tecnológico

| Camada | Tecnologia |
|--------|------------|
| Framework | Flask (Python) |
| ORM | SQLAlchemy |
| Banco | PostgreSQL |
| Migrações | Flask-Migrate (Alembic) |
| Execução Async | Temporal.io |
| Storage | DigitalOcean Spaces |
| Pagamentos | Stripe |
| Auth | JWT + OAuth 2.0 |
| Criptografia | AES-256 |

---

## Estrutura de Diretórios

```
docg-backend/
├── app/
│   ├── __init__.py           # Flask app factory
│   ├── config.py             # Configurações
│   ├── database.py           # SQLAlchemy setup
│   │
│   ├── models/               # Modelos de dados
│   │   ├── organization.py
│   │   ├── workflow.py       # Workflow, WorkflowNode
│   │   ├── execution_step.py # ExecutionStep
│   │   └── ...
│   │
│   ├── controllers/          # Routes da API (Blueprints)
│   │   └── api/v1/
│   │       ├── workflows_controller.py
│   │       ├── organizations_controller.py
│   │       └── ...
│   │
│   ├── apps/                 # Apps modulares (estilo Automatisch)
│   │   ├── base.py           # BaseApp, ExecutionContext, ActionResult
│   │   ├── hubspot/
│   │   ├── google_docs/
│   │   ├── clicksign/
│   │   ├── ai/
│   │   └── ...
│   │
│   ├── engine/               # Engine de execução
│   │   ├── engine.py         # Engine principal
│   │   ├── context.py        # ExecutionContext builder
│   │   ├── compute_parameters.py  # Substituição {{variáveis}}
│   │   ├── action/process.py
│   │   ├── trigger/process.py
│   │   └── steps/iterate.py
│   │
│   ├── services/             # Serviços de negócio
│   │   ├── document_generation/
│   │   ├── ai/
│   │   └── storage/
│   │
│   ├── temporal/             # Temporal.io (execução durável)
│   │   ├── workflows/
│   │   ├── activities/
│   │   └── worker.py
│   │
│   └── utils/                # Utilitários
│       └── encryption.py
│
├── migrations/               # Migrações Alembic
└── requirements.txt
```

---

## Modelo de Dados

### Diagrama Simplificado

```
Organization
    │
    ├── User[]
    ├── Workflow[]
    │       ├── WorkflowNode[]
    │       ├── WorkflowExecution[]
    │       │       └── ExecutionStep[]
    │       └── AIGenerationMapping[]
    │
    ├── Template[]
    ├── DataSourceConnection[]
    └── GeneratedDocument[]
```

### Modelos Principais

#### Organization
```python
id              UUID        # Identificador
name            String      # Nome
plan            String      # free, starter, pro, team, enterprise
documents_limit Integer     # Limite mensal
documents_used  Integer     # Usado no período
stripe_customer_id  String  # Cliente Stripe
```

#### Workflow
```python
id                  UUID    # Identificador
organization_id     UUID    # Organização dona
name                String  # Nome
status              String  # draft, active, paused, archived
trigger_type        String  # manual, webhook, scheduled
source_connection_id UUID   # Conexão de dados (HubSpot, etc)
template_id         UUID    # Template usado
```

#### WorkflowNode
```python
id              UUID    # Identificador
workflow_id     UUID    # Workflow pai
node_type       String  # hubspot, google-docs, clicksign, webhook...
position        Integer # Ordem (1 = primeiro)
config          JSONB   # Configuração do node
structural_type String  # 'single', 'branch', 'paths'
branch_conditions JSONB # Condições para branching
```

#### WorkflowExecution
```python
id                  UUID    # Identificador
workflow_id         UUID    # Workflow executado
status              String  # running, paused, completed, failed
current_node_id     UUID    # Node atual
execution_logs      JSONB   # Logs por step
temporal_workflow_id String # ID no Temporal
```

#### ExecutionStep
```python
id              UUID    # Identificador
execution_id    UUID    # Execução pai
step_id         UUID    # WorkflowNode executado
status          String  # pending, running, success, failed
data_in         JSONB   # Parâmetros de entrada
data_out        JSONB   # Resultado
started_at      DateTime
completed_at    DateTime
```

#### DataSourceConnection
```python
id              UUID    # Identificador
organization_id UUID    # Organização
source_type     String  # hubspot, google, microsoft, clicksign, openai...
credentials     JSONB   # Criptografado (AES-256)
status          String  # active, expired, error
```

---

## Apps Modulares

### Estrutura de um App

```
app/apps/{app_name}/
├── __init__.py          # App class (extends BaseApp)
├── auth.py              # OAuth/API Key config
├── actions/
│   └── {action}.py      # Cada action é uma classe
├── triggers/
│   └── {trigger}.py     # Triggers do app
├── dynamic_data/
│   └── {data}.py        # Dados para dropdowns
└── common/
    └── helpers.py       # Código compartilhado
```

### Apps Disponíveis

| App | Categoria | Descrição |
|-----|-----------|-----------|
| `hubspot` | CRM | Busca objetos, cria/atualiza records |
| `google_docs` | Document | Gera Google Docs |
| `google_slides` | Document | Gera Google Slides |
| `microsoft_word` | Document | Gera Word |
| `microsoft_powerpoint` | Document | Gera PowerPoint |
| `gmail` | Email | Envia emails |
| `outlook` | Email | Envia emails |
| `clicksign` | Signature | Envelopes de assinatura |
| `zapsign` | Signature | Envelopes de assinatura |
| `ai` | AI | Geração de texto via LLM |
| `google_drive` | Storage | Arquivos e pastas |
| `google_forms` | Trigger | Respostas de formulários |
| `storage` | Internal | Upload de templates |
| `stripe` | Payment | Webhooks de pagamento |

### Classes Base

```python
# app/apps/base.py

class BaseApp:
    """App modular com actions, triggers e dynamic_data"""
    name: str
    key: str
    icon_url: str

    def get_actions() -> List[ActionDefinition]
    def get_triggers() -> List[TriggerDefinition]
    def execute_action(action_key, $: ExecutionContext) -> ActionResult

class BaseAction:
    """Action reutilizável"""
    key: str
    name: str
    arguments: List[ActionArgument]

    async def run($: ExecutionContext) -> ActionResult

class BaseTrigger:
    """Trigger reutilizável"""
    key: str
    name: str
    trigger_type: str  # 'webhook', 'polling'

    async def run($: ExecutionContext) -> ActionResult
```

---

## ExecutionContext ($)

Objeto padronizado passado para toda action/trigger.

```python
@dataclass
class ExecutionContext:
    auth: AuthContext           # Credenciais da conexão
    app: AppContext             # Metadados do app
    flow: FlowContext           # ID, nome do workflow
    step: StepContext           # Step atual + parâmetros
    execution: ExecutionMetadata
    http: httpx.AsyncClient     # HTTP já autenticado
    trigger_output: TriggerOutput
    action_output: ActionOutput
    datastore: Datastore        # Storage persistente
```

**Uso:**

```python
async def run(self, $: ExecutionContext) -> ActionResult:
    # Parâmetros já com {{variáveis}} substituídas
    email = $.step.parameters.get('email')

    # HTTP com auth configurado
    response = await $.http.post('/contacts', json={'email': email})

    return ActionResult(
        raw=response.json(),
        data={'id': response.json()['id']}
    )
```

---

## ActionArgument

Schema rico para campos de input. Define como UI renderiza cada campo.

```python
@dataclass
class ActionArgument:
    key: str                    # 'email'
    label: str                  # 'Email'
    type: ArgumentType          # DROPDOWN, STRING, MULTILINE...
    required: bool = False
    variables: bool = True      # Aceita {{step.x.y}}
    source: DynamicDataSource   # Para dropdowns dinâmicos
    depends_on: str             # Campo que controla visibilidade
```

**Tipos:** `STRING`, `NUMBER`, `BOOLEAN`, `DROPDOWN`, `MULTILINE`, `CODE`, `JSON`, `DATE`, `DATETIME`, `FILE`, `HIDDEN`

---

## ActionResult

Output padronizado de todas as actions.

```python
@dataclass
class ActionResult:
    raw: Any              # Resposta bruta da API
    data: Dict[str, Any]  # Campos mapeados
    metadata: dict        # Info extra (pagination, etc)
```

Próximo step acessa via `{{step.{stepId}.id}}` ou `{{step.{stepId}.raw.field}}`.

---

## Fluxo de Execução

```
1. ENTRADA (API/Webhook/HubSpot)
       │
       ▼
2. Engine.run(workflow_id, trigger_data)
       │
       ├── Temporal habilitado? → run_in_background()
       └── Não? → iterate_steps() (síncrono)
       │
       ▼
3. Para cada WorkflowNode (ordenado por position):
       │
       ├── compute_parameters() → substitui {{variáveis}}
       ├── build_execution_context() → monta $
       └── process_step() → executa action/trigger
       │
       ▼
4. Salva ExecutionStep (data_in, data_out)
       │
       ▼
5. Se branch → avalia branch_conditions → próximo node
       │
       ▼
6. Se approval/signature → pausa, aguarda signal
       │
       ▼
7. Fim → status = completed/failed
```

---

## compute_parameters

Substitui variáveis `{{...}}` antes de executar cada step.

| Formato | Exemplo | Descrição |
|---------|---------|-----------|
| `{{step.{id}.{path}}}` | `{{step.abc.email}}` | Valor de step anterior |
| `{{trigger.{path}}}` | `{{trigger.deal.name}}` | Valor do trigger |
| `{{flow.{path}}}` | `{{flow.id}}` | Metadados do workflow |
| `{{execution.{path}}}` | `{{execution.id}}` | Metadados da execução |
| `{{env.{VAR}}}` | `{{env.API_KEY}}` | Variável de ambiente |
| `{{now}}` | - | Data/hora atual |
| `{{uuid}}` | - | UUID aleatório |

---

## Branching (Caminhos Condicionais)

WorkflowNode pode ter `structural_type = 'branch'`:

```python
branch_conditions = [
    {
        "name": "Deal > 10k",
        "conditions": {
            "type": "and",
            "rules": [
                {"field": "{{trigger.amount}}", "operator": ">", "value": 10000}
            ]
        },
        "next_node_id": "uuid-high-value"
    },
    {
        "name": "Default",
        "conditions": None,
        "next_node_id": "uuid-default"
    }
]
```

**Operadores:** `==`, `!=`, `>`, `<`, `>=`, `<=`, `contains`, `not_contains`, `starts_with`, `ends_with`, `is_empty`, `is_not_empty`

---

## API REST

### Base URL

```
/api/v1
```

### Autenticação

```
Authorization: Bearer <token>
```

### Principais Endpoints

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| **Organizations** | | |
| GET | `/organizations/me` | Organização atual |
| PUT | `/organizations/me` | Atualizar |
| **Workflows** | | |
| GET | `/workflows` | Listar |
| POST | `/workflows` | Criar |
| GET | `/workflows/{id}` | Detalhe |
| PUT | `/workflows/{id}` | Atualizar |
| DELETE | `/workflows/{id}` | Deletar |
| POST | `/workflows/{id}/activate` | Ativar |
| **Nodes** | | |
| GET | `/workflows/{id}/nodes` | Listar nodes |
| POST | `/workflows/{id}/nodes` | Criar node |
| PUT | `/workflows/{id}/nodes/{nodeId}` | Atualizar |
| DELETE | `/workflows/{id}/nodes/{nodeId}` | Deletar |
| **Runs** | | |
| GET | `/workflows/{id}/runs` | Listar execuções |
| GET | `/workflows/{id}/runs/{runId}` | Detalhe |
| **Connections** | | |
| GET | `/connections` | Listar |
| POST | `/connections` | Criar |
| POST | `/connections/{id}/test` | Testar |
| DELETE | `/connections/{id}` | Deletar |
| **Templates** | | |
| GET | `/templates` | Listar |
| GET | `/templates/available` | Listar de todas as fontes |
| POST | `/templates/upload` | Upload de arquivo |
| POST | `/templates` | Registrar template existente |
| **Webhooks** | | |
| POST | `/webhooks/{workflowId}/{token}` | Trigger webhook |
| **Approvals** | | |
| GET | `/approvals/{token}` | Status (público) |
| POST | `/approvals/{token}/approve` | Aprovar (público) |
| POST | `/approvals/{token}/reject` | Rejeitar (público) |
| **Billing** | | |
| GET | `/billing/subscription` | Assinatura atual |
| POST | `/checkout/create-session` | Checkout Stripe |

---

## Integrações

### OAuth 2.0

| Provedor | Endpoint Authorize | Callback |
|----------|-------------------|----------|
| Google | `/google-oauth/authorize` | `/google-oauth/callback` |
| Microsoft | `/microsoft/oauth/authorize` | `/microsoft/oauth/callback` |
| HubSpot | `/hubspot-oauth/authorize` | `/hubspot-oauth/callback` |

### Assinatura Digital

| Provedor | Ambientes |
|----------|-----------|
| ClickSign | sandbox, production |
| ZapSign | production |

### Provedores de IA

| Provedor | Modelos |
|----------|---------|
| OpenAI | gpt-3.5-turbo, gpt-4, gpt-4o |
| Anthropic | claude-3-opus, claude-3-sonnet |
| Google | gemini-pro, gemini-1.5-pro |

---

## Temporal.io (Execução Assíncrona)

### Por que usar?

- Execuções longas sem timeout HTTP
- Pausar/retomar (aprovações, assinaturas)
- Retry automático
- Visibilidade no Temporal UI

### Componentes

| Arquivo | Função |
|---------|--------|
| `temporal/client.py` | Conexão com Temporal Server |
| `temporal/service.py` | Funções para API Flask |
| `temporal/worker.py` | Worker que executa workflows |
| `temporal/workflows/docg_workflow.py` | Workflow principal |
| `temporal/activities/` | Activities por tipo |

### Fallback

Se Temporal não configurado → execução síncrona.

---

## Storage (DigitalOcean Spaces)

### Estrutura de Pastas

```
docg/{organization_id}/
├── templates/
│   └── {uuid}.docx
└── outputs/
    ├── {uuid}.docx
    └── {uuid}.pdf
```

### Operações

```python
upload_file(file, key)
generate_signed_url(key, expires=3600)
delete_file(key)
```

---

## Segurança

### Criptografia

- Credenciais criptografadas com AES-256
- Chave em variável de ambiente `ENCRYPTION_KEY`

### Autenticação

- JWT para API
- OAuth 2.0 + PKCE para integrações

### Autorização

- Usuários acessam apenas recursos da sua organização
- Validação de limites de plano

---

## Limites por Plano

| Plano | Usuários | Docs/mês | Workflows |
|-------|----------|----------|-----------|
| Free | 1 | 10 | 5 |
| Starter | 3 | 50 | 5 |
| Pro | 10 | 200 | 20 |
| Team | ∞ | 500 | 50 |
| Enterprise | ∞ | ∞ | ∞ |

---

## Variáveis de Ambiente

```bash
# Database
DATABASE_URL=postgresql://...

# Stripe
STRIPE_SECRET_KEY=sk_...
STRIPE_WEBHOOK_SECRET=whsec_...

# OAuth
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
MICROSOFT_CLIENT_ID=...
MICROSOFT_CLIENT_SECRET=...
HUBSPOT_CLIENT_ID=...
HUBSPOT_CLIENT_SECRET=...

# Encryption
ENCRYPTION_KEY=...

# Temporal
TEMPORAL_ADDRESS=localhost:7233
TEMPORAL_NAMESPACE=default
TEMPORAL_TASK_QUEUE=docg-workflows

# Storage
DO_SPACES_ACCESS_KEY=...
DO_SPACES_SECRET_KEY=...
DO_SPACES_BUCKET=pipehub
DO_SPACES_ENDPOINT=nyc3.digitaloceanspaces.com
```

---

## Comandos

```bash
# Instalar dependências
pip install -r requirements.txt

# Migrações
flask db upgrade          # Aplicar
flask db migrate -m "msg" # Criar nova
flask db downgrade        # Reverter

# Servidor
flask run

# Temporal Worker
python -m app.temporal.worker

# Testes
pytest tests/
```

---

## Arquivos Chave

| Arquivo | Função |
|---------|--------|
| `app/__init__.py` | Flask app factory |
| `app/apps/base.py` | BaseApp, ExecutionContext, ActionResult |
| `app/engine/engine.py` | Engine principal |
| `app/engine/context.py` | Builder do ExecutionContext |
| `app/engine/compute_parameters.py` | Substituição de variáveis |
| `app/models/workflow.py` | Workflow, WorkflowNode |
| `app/models/execution_step.py` | ExecutionStep |
| `app/temporal/workflows/docg_workflow.py` | Workflow Temporal |

---

## Próximos Passos

### Implementação Pendente

1. **Branching no iterate_steps** - Integrar `get_next_node_id()`
2. **Dynamic Fields** - Campos condicionais na UI
3. **Middleware Auth** - beforeRequest hooks nos apps
4. **Test Run Granular** - until_step, mock_data
5. **Datastore Persistente** - Storage real no PostgreSQL

### Melhorias

1. **Validação de Arguments** - required, tipos
2. **Logs Estruturados** - Tracing por execution
3. **WebSockets** - Updates em tempo real
4. **Cache de IA** - Evitar chamadas duplicadas

---

**Última atualização:** 22 de Dezembro de 2025
