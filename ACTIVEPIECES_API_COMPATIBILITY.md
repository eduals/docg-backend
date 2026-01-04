# ActivePieces API Compatibility Plan

> **Objetivo:** Implementar endpoints compatíveis com o frontend ActivePieces UI
> **Princípio:** Sobrescrever backend para atender padrões do frontend (sem retrocompatibilidade)
> **Fonte de Verdade:** Código original do ActivePieces em `/Volumes/dados/CODE/pipehub/activepieces`

---

## 📊 Status Atual

| Categoria | Endpoints Frontend | Endpoints Backend | Gap | Prioridade |
|-----------|-------------------|-------------------|-----|------------|
| Authentication | 9 | 0 | 9 | 🔴 CRITICAL |
| Users | 4 | 8 | Partial | 🟡 HIGH |
| Projects | 7 | 4 | 3 | 🟡 HIGH |
| Flows | 8 | 6 | Partial | 🟠 MEDIUM |
| Pieces | 6 | 2 | 4 | 🟠 MEDIUM |
| Flow Runs | 7 | 2 | 5 | 🟠 MEDIUM |
| Platform Admin | 30+ | 0 | 30+ | 🟢 LOW |

**Total Gap:** ~60 endpoints faltando ou incompatíveis

---

## 🚨 PRIORITY 1: Endpoints Críticos (Bloqueando UI)

### 1.1 Authentication Endpoints
**Status:** ❌ Nenhum endpoint implementado
**Impacto:** Usuário não consegue fazer login/cadastro

#### Endpoints Necessários

##### POST /v1/authentication/sign-in
**Arquivo Frontend:** `/pipehub-ui/react-ui/src/lib/authentication-api.ts:21-26`

**Request:**
```typescript
{
  email: string,
  password: string
}
```

**Response:**
```typescript
{
  id: string,
  email: string,
  firstName: string,
  lastName: string,
  verified: boolean,
  platformRole: string,
  status: string,
  platformId: string,
  projectId: string,
  token: string,  // JWT token
  trackEvents: boolean,
  newsLetter: boolean
}
```

**Implementação:**
- Criar blueprint `app/routes/authentication.py`
- Validar email/senha contra banco de dados
- Gerar JWT token
- Retornar estrutura completa (não apenas `{token: ...}`)

##### POST /v1/authentication/sign-up
**Arquivo Frontend:** `/pipehub-ui/react-ui/src/lib/authentication-api.ts:27-32`

**Request:**
```typescript
{
  email: string,
  password: string,
  firstName: string,
  lastName: string,
  trackEvents: boolean,
  newsLetter: boolean
}
```

**Response:** Mesma estrutura de sign-in

**Implementação:**
- Criar usuário no banco
- Criar organização default (se primeira conta)
- Criar projeto default para o usuário
- Retornar token + dados completos

##### GET /v1/authn/federated/login
**Arquivo Frontend:** `/pipehub-ui/react-ui/src/lib/authentication-api.ts:33-37`

**Query Params:**
```typescript
{
  providerName: 'GOOGLE' | 'GITHUB' | 'SAML'
}
```

**Response:**
```typescript
{
  loginUrl: string  // URL para redirecionar
}
```

**Implementação:**
- Gerar URL de autorização OAuth para o provider
- Suportar Google inicialmente (GITHUB e SAML podem ser futuros)

##### POST /v1/authn/federated/claim
**Arquivo Frontend:** `/pipehub-ui/react-ui/src/lib/authentication-api.ts:41-46`

**Request:**
```typescript
{
  providerName: 'GOOGLE' | 'GITHUB' | 'SAML',
  code: string  // OAuth code
}
```

**Response:** Mesma estrutura de sign-in

**Implementação:**
- Trocar `code` por access token com o provider
- Buscar dados do usuário (email, nome)
- Criar/buscar usuário no banco
- Retornar token + dados

##### POST /v1/otp
**Arquivo Frontend:** `/pipehub-ui/react-ui/src/lib/authentication-api.ts:47-49`

**Request:**
```typescript
{
  email: string,
  type: 'EMAIL_VERIFICATION' | 'PASSWORD_RESET'
}
```

**Response:** void (204 No Content)

**Implementação:**
- Gerar OTP (6 dígitos)
- Armazenar no banco com TTL (10 minutos)
- Enviar email com OTP

##### POST /v1/authn/local/reset-password
**Arquivo Frontend:** `/pipehub-ui/react-ui/src/lib/authentication-api.ts:50-52`

**Request:**
```typescript
{
  identityId: string,
  otp: string,
  newPassword: string
}
```

**Response:** void (204 No Content)

**Implementação:**
- Validar OTP
- Atualizar senha do usuário
- Invalidar OTP usado

##### POST /v1/authn/local/verify-email
**Arquivo Frontend:** `/pipehub-ui/react-ui/src/lib/authentication-api.ts:53-55`

**Request:**
```typescript
{
  identityId: string,
  otp: string
}
```

**Response:**
```typescript
{
  email: string,
  firstName: string,
  verified: boolean
}
```

**Implementação:**
- Validar OTP
- Marcar email como verificado
- Retornar dados do usuário

##### GET /v1/project-members/role
**Arquivo Frontend:** `/pipehub-ui/react-ui/src/lib/authentication-api.ts:38-40`

**Query Params:**
```typescript
{
  projectId: string
}
```

**Response:**
```typescript
ProjectRole | null
```

**Implementação:**
- Buscar role do usuário no projeto
- Retornar permissões

##### POST /v1/authentication/switch-platform
**Arquivo Frontend:** `/pipehub-ui/react-ui/src/lib/authentication-api.ts:56-61`

**Request:**
```typescript
{
  platformId: string
}
```

**Response:** Mesma estrutura de sign-in (com novo token)

**Implementação:**
- Validar acesso ao platform
- Gerar novo token com platformId
- Retornar token atualizado

---

### 1.2 Users Endpoints
**Status:** ⚠️ Parcialmente implementado (mock data)
**Impacto:** Dados de usuário não aparecem corretamente

#### GET /v1/users/{id}
**Status Atual:** Retorna mock data (sem autenticação)

**Arquivo Atual:** `/docg-backend/app/routes/users.py:46-60`

**Problema:**
```python
# Código atual
def get_user(user_id):
    # TODO: Re-enable auth after ActivePieces UI is configured
    # Temporary mock for ActivePieces UI compatibility
    return jsonify({
        'id': user_id,
        'email': 'user@example.com',
        'firstName': 'Demo',
        'lastName': 'User',
        ...
    })
```

**Correção Necessária:**
```python
@users_bp.route('/<user_id>', methods=['GET'])
@require_auth
@require_org
def get_user(user_id):
    """Retorna dados reais do usuário do banco"""
    user = User.query.filter_by(
        id=user_id,
        organization_id=g.organization_id
    ).first_or_404()

    return jsonify({
        'id': user.id,
        'email': user.email,
        'firstName': user.first_name,
        'lastName': user.last_name,
        'status': user.status or 'ACTIVE',
        'platformRole': user.role or 'MEMBER',
        'verified': True,
        'created': user.created_at.isoformat(),
        'updated': user.updated_at.isoformat(),
    })
```

**Campos Faltantes no Model User:**
- `first_name` (adicionar)
- `last_name` (adicionar)
- `status` (adicionar: ACTIVE, INACTIVE)
- `platform_role` (adicionar: OWNER, ADMIN, MEMBER)
- `verified` (adicionar boolean)

#### GET /v1/users/projects
**Arquivo Frontend:** `/pipehub-ui/react-ui/src/lib/project-api.ts`

**Status:** ❌ Não existe (backend tem `/v1/projects` mas estrutura diferente)

**Response Esperado:**
```typescript
{
  data: ProjectWithLimits[],
  next: string | null,
  previous: string | null
}

ProjectWithLimits = {
  id: string,
  displayName: string,
  platformId: string,
  externalId: string,
  created: string,
  updated: string,
  plan: {
    tasks: number,
    aiTokens: number,
    minimumPollingInterval: number
  },
  usage: {
    tasks: number,
    aiTokens: number
  }
}
```

**Implementação:**
- Buscar projetos do usuário autenticado
- Retornar estrutura de paginação (cursor-based, não offset)
- Incluir limites e uso

---

### 1.3 Projects Endpoints
**Status:** ⚠️ Estrutura incompatível com frontend

#### GET /v1/users/projects/{projectId}
**Status:** ❌ Não existe

**Response:**
```typescript
{
  id: string,
  displayName: string,
  platformId: string,
  created: string,
  updated: string,
  plan: {
    tasks: number,
    aiTokens: number,
    minimumPollingInterval: number
  },
  usage: {
    tasks: number,
    aiTokens: number
  }
}
```

#### POST /v1/projects
**Status:** ✅ Existe mas precisa validar estrutura

**Request Esperado:**
```typescript
{
  displayName: string,
  externalId?: string
}
```

#### POST /v1/projects/{projectId}
**Status:** ⚠️ Backend usa PUT, frontend usa POST

**Correção:** Aceitar tanto PUT quanto POST

---

## 🟡 PRIORITY 2: Endpoints Importantes (UI Parcial)

### 2.1 Flows Endpoints

#### Estrutura de Flow no ActivePieces
**Tipo:** `PopulatedFlow`

```typescript
{
  id: string,
  projectId: string,
  folderId: string | null,
  version: {
    id: string,
    flowId: string,
    displayName: string,
    trigger: TriggerSettings,
    updatedBy: string,
    valid: boolean,
    state: 'LOCKED' | 'DRAFT',
    created: string,
    updated: string
  },
  publishedVersionId: string | null,
  schedule: {
    type: 'CRON_EXPRESSION',
    cronExpression: string,
    timezone: string
  } | null,
  status: 'ENABLED' | 'DISABLED',
  created: string,
  updated: string
}
```

**Backend Atual:** Estrutura de `Workflow` é diferente

**Ação:**
1. Criar adapter `FlowAdapter` para converter `Workflow` ↔ `PopulatedFlow`
2. Criar migration para adicionar campos faltantes em `Workflow`:
   - `folder_id` (FK para folders)
   - `published_version_id` (FK para flow_versions)
   - `schedule` (JSONB)
   - `status` (ENUM: ENABLED, DISABLED)

#### GET /v1/flows
**Response:**
```typescript
{
  data: PopulatedFlow[],
  next: string | null,
  previous: string | null
}
```

**Query Params:**
- `projectId` (required)
- `folderId` (optional)
- `status` (optional: ENABLED, DISABLED)
- `limit` (default: 10)
- `cursor` (pagination)

#### POST /v1/flows
**Request:**
```typescript
{
  displayName: string,
  projectId: string,
  folderId?: string
}
```

**Response:** `PopulatedFlow`

**Ação:** Criar flow + versão draft inicial

#### POST /v1/flows/{flowId}
**Request:** `FlowOperationRequest`

Pode ser:
- UPDATE_TRIGGER
- ADD_ACTION
- UPDATE_ACTION
- DELETE_ACTION
- DUPLICATE_ACTION
- MOVE_ACTION
- LOCK_FLOW
- CHANGE_NAME
- CHANGE_FOLDER
- CHANGE_STATUS

**Implementação:** Flow builder operations (complexo)

#### GET /v1/flows/{flowId}/versions
**Response:**
```typescript
{
  data: FlowVersionMetadata[],
  next: string | null,
  previous: string | null
}
```

#### DELETE /v1/flows/{flowId}
**Status:** ✅ Implementar soft delete

#### GET /v1/flows/count
**Query Params:**
```typescript
{
  projectId: string,
  folderId?: string,
  status?: 'ENABLED' | 'DISABLED'
}
```

**Response:** `number`

---

### 2.2 Flow Runs Endpoints

#### GET /v1/flow-runs
**Query Params:**
```typescript
{
  projectId: string,
  flowId?: string,
  status?: 'RUNNING' | 'SUCCEEDED' | 'FAILED' | 'QUOTA_EXCEEDED',
  limit?: number,
  cursor?: string
}
```

**Response:**
```typescript
{
  data: FlowRun[],
  next: string | null,
  previous: string | null
}
```

**FlowRun:**
```typescript
{
  id: string,
  projectId: string,
  flowId: string,
  flowVersionId: string,
  flowDisplayName: string,
  status: 'RUNNING' | 'SUCCEEDED' | 'FAILED',
  startTime: string,
  finishTime: string | null,
  duration: number | null,
  steps: {
    [stepName: string]: {
      type: string,
      status: 'SUCCEEDED' | 'FAILED' | 'RUNNING',
      input: unknown,
      output: unknown,
      duration: number
    }
  }
}
```

**Mapeamento:** `WorkflowExecution` → `FlowRun`

#### GET /v1/flow-runs/{id}
**Response:** `FlowRun` (populated)

#### POST /v1/flow-runs/retry
**Request:**
```typescript
{
  flowRunIds: string[]
}
```

**Response:** `FlowRun[]`

#### POST /v1/flow-runs/{flowRunId}/retry
**Request:**
```typescript
{
  strategy: 'FROM_FAILED_STEP' | 'ON_LATEST_VERSION'
}
```

**Response:** `FlowRun`

---

### 2.3 Pieces Endpoints

#### GET /v1/pieces
**Query Params:**
```typescript
{
  projectId: string,
  includeHidden?: boolean,
  release?: string
}
```

**Response:**
```typescript
PieceMetadataModelSummary[]

{
  name: string,
  displayName: string,
  description: string,
  logoUrl: string,
  version: string,
  minimumSupportedRelease: string,
  maximumSupportedRelease: string,
  auth: unknown,
  actions: Record<string, PieceAction>,
  triggers: Record<string, PieceTrigger>,
  categories: string[]
}
```

**Implementação:**
- Ler metadados de pieces instalados
- Retornar estrutura padronizada
- Suportar filtro por projeto

#### GET /v1/pieces/{name}
**Query Params:**
```typescript
{
  version?: string,
  projectId: string
}
```

**Response:** `PieceMetadataModel` (detalhado)

#### POST /v1/pieces/options
**Request:**
```typescript
{
  projectId: string,
  pieceType: string,
  pieceName: string,
  pieceVersion: string,
  stepName: string,
  propertyName: string,
  input: Record<string, unknown>
}
```

**Response:**
```typescript
{
  options: Array<{ label: string, value: unknown }>,
  disabled: boolean,
  placeholder?: string
}
```

**Implementação:**
- Executar função `options` do piece
- Dinâmico (dropdowns dependentes)

---

## 🟠 PRIORITY 3: Endpoints Secundários

### 3.1 Folders
✅ **Backend já implementado** em `/api/v1/folders`

**Validar:**
- Estrutura de response compatível
- Paginação cursor-based

### 3.2 Templates
✅ **Backend já implementado** em `/api/v1/templates`

**Adaptar:**
- Renomear para match ActivePieces naming
- Response structure

### 3.3 Triggers & Sample Data

#### POST /v1/test-trigger
**Request:**
```typescript
{
  flowVersionId: string,
  testStrategy: 'SIMULATION' | 'TEST_FUNCTION'
}
```

**Response:**
```typescript
{
  data: TriggerEventWithPayload[],
  next: string | null,
  previous: string | null
}
```

#### GET /v1/trigger-events
**Query Params:**
```typescript
{
  flowId: string,
  limit?: number,
  cursor?: string
}
```

#### GET /v1/sample-data
**Query Params:**
```typescript
{
  flowId: string,
  stepName: string
}
```

**Response:** `unknown` (dados de amostra para o step)

---

## 🟢 PRIORITY 4: Admin Endpoints (Não Urgente)

### 4.1 Platform Admin
- `/v1/signing-keys` (lista, create, delete)
- `/v1/ai-providers` (lista, upsert, delete)
- `/v1/api-keys` (lista, create, delete)
- `/v1/worker-machines` (lista)
- `/v1/audit-events` (lista)
- `/v1/analytics` (get, refresh, update)
- `/v1/project-roles` (CRUD)

### 4.2 Project Members
- `/v1/project-members` (CRUD)
- `/v1/project-members/{memberId}` (update role)

### 4.3 Billing
- `/v1/platform-billing/info`
- `/v1/platform-billing/portal`
- `/v1/platform-billing/create-checkout-session`

### 4.4 Git Sync
- `/v1/git-repos` (get, configure, disconnect, push)

---

## 📁 Estrutura de Arquivos Proposta

```
docg-backend/
├── app/
│   ├── routes/
│   │   ├── authentication.py          # NEW - Auth endpoints
│   │   ├── users.py                   # UPDATE - Fix mock data
│   │   ├── projects.py                # UPDATE - Add /users/projects
│   │   ├── flows.py                   # NEW - ActivePieces flows
│   │   ├── flow_versions.py           # NEW
│   │   ├── flow_runs.py               # NEW
│   │   ├── pieces.py                  # NEW
│   │   ├── folders.py                 # EXISTS - Validate
│   │   ├── templates.py               # EXISTS - Adapt
│   │   └── ...
│   │
│   ├── models/
│   │   ├── user.py                    # UPDATE - Add fields
│   │   ├── project.py                 # UPDATE - Add fields
│   │   ├── flow.py                    # NEW
│   │   ├── flow_version.py            # NEW
│   │   ├── flow_run.py                # NEW (ou renomear workflow_execution)
│   │   ├── piece.py                   # NEW
│   │   └── ...
│   │
│   ├── adapters/                      # NEW
│   │   ├── flow_adapter.py            # Workflow ↔ Flow
│   │   ├── execution_adapter.py       # WorkflowExecution ↔ FlowRun
│   │   └── user_adapter.py            # User ↔ ActivePieces User
│   │
│   └── utils/
│       ├── auth.py                    # UPDATE - JWT generation
│       └── pagination.py              # NEW - Cursor-based pagination
│
├── migrations/
│   └── versions/
│       ├── add_user_fields.py         # Migration 1
│       ├── add_flow_tables.py         # Migration 2
│       └── add_project_fields.py      # Migration 3
│
└── ACTIVEPIECES_API_COMPATIBILITY.md  # Este arquivo
```

---

## 🔧 Models - Campos Necessários

### User Model Updates
```python
class User(db.Model):
    # Campos existentes
    id = db.Column(UUID(as_uuid=True), primary_key=True)
    email = db.Column(String(255), unique=True, nullable=False)
    name = db.Column(String(255))  # DEPRECAR

    # Novos campos ActivePieces
    first_name = db.Column(String(100))
    last_name = db.Column(String(100))
    status = db.Column(String(20), default='ACTIVE')  # ACTIVE, INACTIVE
    platform_role = db.Column(String(20), default='MEMBER')  # OWNER, ADMIN, MEMBER
    verified = db.Column(Boolean, default=False)
    track_events = db.Column(Boolean, default=True)
    news_letter = db.Column(Boolean, default=False)
    external_id = db.Column(String(255), nullable=True)  # Para OAuth
```

### Project Model Updates
```python
class Project(db.Model):
    # Campos existentes
    id = db.Column(UUID(as_uuid=True), primary_key=True)
    name = db.Column(String(255))  # RENOMEAR para display_name

    # Novos campos ActivePieces
    display_name = db.Column(String(255), nullable=False)
    platform_id = db.Column(UUID(as_uuid=True), ForeignKey('platform.id'))
    external_id = db.Column(String(255), nullable=True)

    # Plano e limites
    plan_tasks = db.Column(Integer, default=1000)
    plan_ai_tokens = db.Column(Integer, default=10000)
    plan_min_polling_interval = db.Column(Integer, default=60)  # segundos

    # Uso atual
    usage_tasks = db.Column(Integer, default=0)
    usage_ai_tokens = db.Column(Integer, default=0)
```

### New: Flow Model
```python
class Flow(db.Model):
    __tablename__ = 'flows'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = db.Column(UUID(as_uuid=True), ForeignKey('projects.id'), nullable=False)
    folder_id = db.Column(UUID(as_uuid=True), ForeignKey('folders.id'), nullable=True)
    published_version_id = db.Column(UUID(as_uuid=True), ForeignKey('flow_versions.id'))

    schedule = db.Column(JSONB, nullable=True)  # {type, cronExpression, timezone}
    status = db.Column(String(20), default='DISABLED')  # ENABLED, DISABLED

    created_at = db.Column(DateTime, default=datetime.utcnow)
    updated_at = db.Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

### New: FlowVersion Model
```python
class FlowVersion(db.Model):
    __tablename__ = 'flow_versions'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    flow_id = db.Column(UUID(as_uuid=True), ForeignKey('flows.id'), nullable=False)
    display_name = db.Column(String(255), nullable=False)

    trigger = db.Column(JSONB, nullable=False)  # TriggerSettings
    updated_by = db.Column(UUID(as_uuid=True), ForeignKey('users.id'))
    valid = db.Column(Boolean, default=True)
    state = db.Column(String(20), default='DRAFT')  # DRAFT, LOCKED

    created_at = db.Column(DateTime, default=datetime.utcnow)
    updated_at = db.Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

### FlowRun Model (renomear WorkflowExecution)
```python
class FlowRun(db.Model):
    __tablename__ = 'flow_runs'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = db.Column(UUID(as_uuid=True), ForeignKey('projects.id'), nullable=False)
    flow_id = db.Column(UUID(as_uuid=True), ForeignKey('flows.id'), nullable=False)
    flow_version_id = db.Column(UUID(as_uuid=True), ForeignKey('flow_versions.id'))
    flow_display_name = db.Column(String(255))

    status = db.Column(String(20))  # RUNNING, SUCCEEDED, FAILED, QUOTA_EXCEEDED
    start_time = db.Column(DateTime, default=datetime.utcnow)
    finish_time = db.Column(DateTime, nullable=True)
    duration = db.Column(Integer, nullable=True)  # milissegundos

    steps = db.Column(JSONB, default={})  # {stepName: {status, input, output, duration}}

    created_at = db.Column(DateTime, default=datetime.utcnow)
    updated_at = db.Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

---

## 🔐 Autenticação e Autorização

### JWT Token Structure
```typescript
{
  // Payload
  userId: string,
  email: string,
  platformId: string,
  projectId: string,  // Projeto atual
  platformRole: string,

  // Standard claims
  iat: number,
  exp: number,
  iss: 'pipehub'
}
```

### Headers Necessários
- `Authorization: Bearer <token>`
- `X-Organization-ID: <uuid>` (opcional, pode vir do token)

### Auth Decorators
```python
@require_auth          # Valida JWT
@require_org           # Valida organização
@require_project       # Valida projeto (novo)
@require_admin         # Valida admin role
```

---

## 📦 Pagination - Cursor Based

### ActivePieces usa cursor-based, não offset

**Response Structure:**
```typescript
{
  data: T[],
  next: string | null,      // Cursor para próxima página
  previous: string | null   // Cursor para página anterior
}
```

**Query Params:**
```typescript
{
  limit: number = 10,
  cursor?: string
}
```

**Implementação:**
```python
def paginate_cursor(query, limit, cursor=None):
    """
    Cursor = base64({id: last_id, created_at: timestamp})
    """
    if cursor:
        decoded = base64.urlsafe_b64decode(cursor)
        last_id, last_created = parse_cursor(decoded)
        query = query.filter(
            (Model.created_at < last_created) |
            ((Model.created_at == last_created) & (Model.id < last_id))
        )

    items = query.order_by(Model.created_at.desc(), Model.id.desc()).limit(limit + 1).all()

    has_next = len(items) > limit
    if has_next:
        items = items[:limit]

    next_cursor = None
    if has_next:
        last = items[-1]
        next_cursor = encode_cursor(last.id, last.created_at)

    return {
        'data': [item.to_dict() for item in items],
        'next': next_cursor,
        'previous': None  # Implementar se necessário
    }
```

---

## 🎯 Plano de Implementação

### Fase 1: Authentication (1-2 dias)
**Objetivo:** Permitir login/cadastro

1. Criar blueprint `authentication.py`
2. Implementar POST /v1/authentication/sign-in
3. Implementar POST /v1/authentication/sign-up
4. Implementar geração de JWT com estrutura completa
5. Testar login no frontend

**Arquivos:**
- `app/routes/authentication.py` (novo)
- `app/utils/auth.py` (update JWT)
- `app/models/user.py` (migration: add fields)

### Fase 2: Users & Projects (1 dia)
**Objetivo:** Dados de usuário e projetos aparecem corretamente

1. Adicionar campos em User model
2. Corrigir GET /v1/users/{id} (remover mock)
3. Implementar GET /v1/users/projects
4. Implementar GET /v1/users/projects/{projectId}
5. Adicionar campos em Project model

**Arquivos:**
- `app/models/user.py` (migration)
- `app/models/project.py` (migration)
- `app/routes/users.py` (update)
- `app/routes/projects.py` (update)

### Fase 3: Flows Core (2-3 dias)
**Objetivo:** Flow builder funcional

1. Criar models Flow, FlowVersion, FlowRun
2. Criar adapters Workflow ↔ Flow
3. Implementar GET /v1/flows
4. Implementar POST /v1/flows
5. Implementar GET /v1/flows/{flowId}
6. Implementar GET /v1/flows/{flowId}/versions
7. Implementar DELETE /v1/flows/{flowId}

**Arquivos:**
- `app/models/flow.py` (novo)
- `app/models/flow_version.py` (novo)
- `app/adapters/flow_adapter.py` (novo)
- `app/routes/flows.py` (novo)

### Fase 4: Flow Operations (2-3 dias)
**Objetivo:** Edição de flows

1. Implementar POST /v1/flows/{flowId} (flow operations)
2. Suportar UPDATE_TRIGGER
3. Suportar ADD_ACTION
4. Suportar UPDATE_ACTION
5. Suportar DELETE_ACTION
6. Suportar CHANGE_NAME, CHANGE_STATUS

**Arquivos:**
- `app/routes/flows.py` (update)
- `app/services/flow_operations.py` (novo)

### Fase 5: Flow Runs (1-2 dias)
**Objetivo:** Execuções aparecem corretamente

1. Criar adapter WorkflowExecution ↔ FlowRun
2. Implementar GET /v1/flow-runs
3. Implementar GET /v1/flow-runs/{id}
4. Implementar POST /v1/flow-runs/retry

**Arquivos:**
- `app/adapters/execution_adapter.py` (novo)
- `app/routes/flow_runs.py` (novo)

### Fase 6: Pieces (2 dias)
**Objetivo:** Pieces aparecem no builder

1. Criar registry de pieces
2. Implementar GET /v1/pieces
3. Implementar GET /v1/pieces/{name}
4. Implementar POST /v1/pieces/options (dynamic properties)

**Arquivos:**
- `app/pieces/registry.py` (novo)
- `app/routes/pieces.py` (novo)

### Fase 7: Pagination & Utils (1 dia)
**Objetivo:** Paginação consistente

1. Implementar cursor-based pagination
2. Atualizar todos os endpoints com paginação
3. Testar performance

**Arquivos:**
- `app/utils/pagination.py` (novo)

### Fase 8: Polish & Testing (1-2 dias)
**Objetivo:** Garantir compatibilidade total

1. Testar todas as rotas no frontend
2. Corrigir bugs de estrutura
3. Validar campos obrigatórios
4. Documentar diferenças com ActivePieces original

---

## 📊 Checklist de Compatibilidade

### Authentication ✅/❌
- [ ] POST /v1/authentication/sign-in
- [ ] POST /v1/authentication/sign-up
- [ ] GET /v1/authn/federated/login
- [ ] POST /v1/authn/federated/claim
- [ ] POST /v1/otp
- [ ] POST /v1/authn/local/reset-password
- [ ] POST /v1/authn/local/verify-email
- [ ] GET /v1/project-members/role
- [ ] POST /v1/authentication/switch-platform

### Users ✅/❌
- [ ] GET /v1/users/{id} (dados reais, não mock)
- [ ] GET /v1/users
- [ ] GET /v1/users/projects
- [ ] GET /v1/users/projects/{projectId}

### Projects ✅/❌
- [ ] GET /v1/projects
- [ ] POST /v1/projects
- [ ] GET /v1/projects/{id}
- [ ] POST /v1/projects/{id}
- [ ] DELETE /v1/projects/{id}

### Flows ✅/❌
- [ ] GET /v1/flows
- [ ] POST /v1/flows
- [ ] GET /v1/flows/{id}
- [ ] POST /v1/flows/{id}
- [ ] DELETE /v1/flows/{id}
- [ ] GET /v1/flows/{id}/versions
- [ ] GET /v1/flows/count

### Flow Runs ✅/❌
- [ ] GET /v1/flow-runs
- [ ] GET /v1/flow-runs/{id}
- [ ] POST /v1/flow-runs/retry
- [ ] POST /v1/flow-runs/{id}/retry

### Pieces ✅/❌
- [ ] GET /v1/pieces
- [ ] GET /v1/pieces/{name}
- [ ] POST /v1/pieces/options

### Folders ✅/❌
- [x] GET /v1/folders (existe)
- [x] POST /v1/folders (existe)
- [ ] Validar estrutura de response

### Templates ✅/❌
- [x] GET /v1/templates (existe)
- [ ] Adaptar response structure

---

## 🚀 Resumo Executivo

**Total de Endpoints a Implementar/Corrigir:** ~40 endpoints críticos

**Tempo Estimado:** 10-15 dias de desenvolvimento

**Impacto:**
- ✅ UI do ActivePieces funcionará 100%
- ✅ Login/cadastro funcionais
- ✅ Flow builder completo
- ✅ Execuções visíveis
- ✅ Pieces disponíveis

**Princípio:**
- Backend será **sobrescrito** para seguir padrões ActivePieces
- **Sem retrocompatibilidade** com estrutura antiga
- Fonte de verdade: código original ActivePieces

---

**Próximo Passo:** Aprovar este plano e começar implementação pela Fase 1 (Authentication)
