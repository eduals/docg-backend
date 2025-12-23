# CLAUDE.md - DocG Backend Architecture Guide

> **Versão:** 2.2 - Post-MVP Features
> **Atualizado:** 23 de Dezembro de 2025
> **Status:** ✅ Implementação Completa (14/14 features v2.0 + Tags v2.1 + Post-MVP v2.2)
> **Propósito:** Referência arquitetural completa para desenvolvimento

---

## 📚 Índice

1. [O Que É o DocG](#o-que-é-o-docg)
2. [Stack Tecnológico](#stack-tecnológico)
3. [Estrutura de Diretórios](#estrutura-de-diretórios)
4. [Modelo de Dados](#modelo-de-dados-principal)
5. [Execução v2.0](#execução-v20-features-implementadas)
6. [Sistema de Tags Avançadas](#sistema-de-tags-avançadas)
7. [HubSpot Expandido](#hubspot-expandido)
8. [API REST](#api-rest-principal)
9. [SSE e Realtime](#sse-server-sent-events)
10. [Variáveis de Ambiente](#variáveis-de-ambiente)
11. [Comandos Úteis](#comandos-úteis)
12. [Erros Comuns](#️-erros-comuns-e-soluções)
13. [Testes e Verificação](#testes-e-verificação)

---

## O Que É o DocG?

Sistema de **geração automatizada de documentos** que:

1. **Extrai dados** de CRMs (HubSpot) ou webhooks
2. **Gera documentos** (Google Docs, Word, Slides, PowerPoint)
3. **Coleta assinaturas** digitais (ClickSign, ZapSign)
4. **Envia por email** (Gmail, Outlook)
5. **Orquestra tudo** via workflows visuais com **observabilidade completa**

### Diferencial v2.0

- ✅ **Run State unificado** - 12 status de execução
- ✅ **Preflight checks** - Validação antes de executar
- ✅ **SSE com replay** - Real-time com recuperação de eventos
- ✅ **Logs estruturados** - Consultáveis e filtráveis
- ✅ **Audit trail** - Rastreamento imutável para compliance
- ✅ **Pause/Resume** - Controle total da execução

### Diferencial v2.1 (Tags + HubSpot)

- ✅ **Tags Avançadas** - Pipes, fórmulas, condicionais, loops
- ✅ **Preview de Tags** - Validação antes de gerar documento
- ✅ **Multi-CRM** - Normalização para HubSpot, Webhook, Forms, Stripe
- ✅ **HubSpot Tickets** - CRUD completo
- ✅ **HubSpot Line Items** - Busca e criação
- ✅ **Associações** - Acesso a objetos relacionados

### Diferencial v2.2 (Post-MVP)

- ✅ **Dry-run & Until Phase** - Execução preview sem persistência
- ✅ **Signature Events SSE** - Eventos granulares por signatário
- ✅ **Loops em Google Docs** - Duplicação automática de linhas de tabela

---

## Stack Tecnológico

| Camada | Tecnologia | Versão | Uso |
|--------|------------|--------|-----|
| **Framework** | Flask | 3.0.0 | API REST |
| **ORM** | SQLAlchemy | 2.x | Modelagem de dados |
| **Database** | PostgreSQL | 14+ | Persistência (JSONB, UUID) |
| **Migrations** | Flask-Migrate (Alembic) | - | Versionamento de schema |
| **Async Workflows** | Temporal.io | - | Orquestração assíncrona |
| **Streams/Cache** | Redis Streams | 8.4.0+ | SSE com replay |
| **Storage** | DigitalOcean Spaces | - | S3-compatible storage |
| **Pagamentos** | Stripe | - | Checkout e webhooks |
| **Auth** | JWT + OAuth 2.0 | - | Autenticação/autorização |
| **Criptografia** | AES-256 | - | Credentials em repouso |
| **HTTP Client** | httpx | - | Async HTTP |

---

## Estrutura de Diretórios

```
docg-backend/
├── app/
│   ├── __init__.py              # Flask app factory + blueprints
│   ├── config.py                # Configurações (env vars)
│   ├── database.py              # SQLAlchemy setup
│   │
│   ├── models/                  # SQLAlchemy Models (10 models)
│   │   ├── organization.py      # Organization, User
│   │   ├── workflow.py          # Workflow, WorkflowNode
│   │   ├── execution.py         # WorkflowExecution (+ Run State v2.0)
│   │   ├── execution_step.py    # ExecutionStep (+ error contexts)
│   │   ├── execution_log.py     # ExecutionLog (NEW - logs estruturados)
│   │   ├── audit_event.py       # AuditEvent (NEW - audit trail)
│   │   ├── connection.py        # DataSourceConnection
│   │   ├── template.py          # Template
│   │   ├── document.py          # GeneratedDocument
│   │   ├── approval.py          # WorkflowApproval
│   │   ├── signature.py         # SignatureRequest
│   │   └── datastore.py         # WorkflowDatastore
│   │
│   ├── controllers/             # API Routes (Blueprints)
│   │   └── api/v1/
│   │       ├── executions/      # NEW - Execution endpoints v2.0
│   │       │   ├── __init__.py  # Blueprint registration
│   │       │   ├── logs.py      # GET /executions/{id}/logs
│   │       │   ├── audit.py     # GET /executions/{id}/audit
│   │       │   ├── steps.py     # GET /executions/{id}/steps
│   │       │   ├── control.py   # POST /executions/{id}/resume|cancel|retry
│   │       │   └── preflight.py # Preflight endpoints
│   │       ├── workflows_controller.py
│   │       ├── organizations_controller.py
│   │       ├── connections_controller.py
│   │       ├── templates_controller.py
│   │       ├── approvals_controller.py
│   │       └── apps/            # Apps metadata endpoints
│   │
│   ├── apps/                    # Apps Modulares (14 apps)
│   │   ├── base.py              # BaseApp, ExecutionContext, ActionResult
│   │   ├── hubspot/             # CRM
│   │   ├── google_docs/         # Documents
│   │   ├── google_slides/       # Presentations
│   │   ├── google_drive/        # Storage
│   │   ├── google_forms/        # Form responses
│   │   ├── microsoft_word/      # Documents
│   │   ├── microsoft_powerpoint/ # Presentations
│   │   ├── gmail/               # Email
│   │   ├── outlook/             # Email
│   │   ├── clicksign/           # Signatures
│   │   ├── zapsign/             # Signatures
│   │   ├── ai/                  # LLM processing
│   │   ├── stripe/              # Payments
│   │   └── storage/             # Generic storage
│   │
│   ├── engine/                  # Engine de Execução
│   │   ├── engine.py            # Engine.run() - ponto de entrada (+ dry_run, until_phase)
│   │   ├── phases.py            # NEW v2.2 - ExecutionPhase enum
│   │   ├── context.py           # Build ExecutionContext
│   │   ├── compute_parameters.py # Substituição {{variáveis}} + tags avançadas
│   │   ├── validate_parameters.py # Validação de arguments
│   │   ├── action/
│   │   │   └── process.py       # process_action_step()
│   │   ├── trigger/
│   │   │   └── process.py       # process_trigger_step()
│   │   ├── steps/
│   │   │   └── iterate.py       # iterate_steps() - loop principal (+ phase detection)
│   │   └── flow/
│   │       └── context.py       # FlowContext, get_next_node()
│   │
│   ├── tags/                    # NEW - Sistema de Tags Avançadas
│   │   ├── __init__.py          # TagProcessor principal
│   │   ├── parser/              # Lexer, AST, Parser
│   │   │   ├── lexer.py         # Tokenização (40+ tokens)
│   │   │   ├── ast.py           # AST nodes
│   │   │   └── parser.py        # Parser principal
│   │   ├── transforms/          # Transforms (pipes)
│   │   │   ├── base.py          # TransformRegistry
│   │   │   ├── text.py          # upper, lower, truncate, concat
│   │   │   ├── date.py          # format com locale
│   │   │   └── number.py        # currency, number, round
│   │   ├── engine/              # Avaliação
│   │   │   ├── evaluator.py     # TagEvaluator
│   │   │   ├── formula.py       # FormulaEvaluator (AST seguro)
│   │   │   └── functions.py     # SUM, ROUND, IF, AVG, etc
│   │   ├── context/             # Contexto Multi-CRM
│   │   │   ├── builder.py       # ContextBuilder
│   │   │   ├── normalizer.py    # HubSpot, Webhook, Forms, Stripe
│   │   │   └── global_vars.py   # $timestamp, $date, etc
│   │   └── preview/             # Preview de tags
│   │       └── service.py       # TagPreviewService
│   │
│   ├── temporal/                # Temporal.io (Async)
│   │   ├── client.py            # Temporal client
│   │   ├── service.py           # Helpers para Flask
│   │   ├── config.py            # Task queues config
│   │   ├── worker.py            # Worker principal
│   │   ├── workflows/
│   │   │   └── docg_workflow.py # DocGWorkflow (+ signals v2.0)
│   │   └── activities/
│   │       ├── base.py          # Activities comuns
│   │       ├── trigger.py       # Extração de dados
│   │       ├── document.py      # Geração de docs
│   │       ├── approval.py      # Aprovações
│   │       ├── signature.py     # Assinaturas
│   │       ├── email.py         # Envio de emails
│   │       ├── webhook.py       # Webhooks de saída
│   │       └── preflight.py     # NEW - Validação prévia
│   │
│   ├── services/                # Serviços de Negócio
│   │   ├── document_generation/ # Geração de docs
│   │   │   ├── loop_parser.py   # NEW v2.2 - Parser de loops {{FOR}}
│   │   │   └── table_loops.py   # NEW v2.2 - Duplicação de linhas
│   │   ├── ai/                  # Integração com LLMs
│   │   ├── storage/             # Upload/download S3
│   │   ├── sse_publisher.py     # SSE Publisher (Redis Streams + Schema v1)
│   │   ├── execution_logger.py  # NEW v2.0 - Logs estruturados
│   │   ├── audit_service.py     # NEW v2.0 - Audit helper
│   │   └── recommended_actions.py # NEW v2.0 - CTAs para issues
│   │
│   ├── routes/                  # Rotas especiais
│   │   └── sse.py               # SSE endpoint (Streams + replay)
│   │
│   ├── serializers/             # JSON serialization
│   │   └── execution_serializer.py # Atualizado com Run State v2.0
│   │
│   └── utils/
│       ├── encryption.py        # AES-256 para credentials
│       └── auth.py              # JWT helpers
│
├── migrations/                  # Alembic migrations
│   └── versions/
│       ├── u1v2w3x4y5z6_add_run_state_fields.py
│       ├── v1w2x3y4z5a6_create_execution_logs.py
│       ├── w2x3y4z5a6b7_create_audit_events.py
│       └── x3y4z5a6b7c8_add_error_fields_execution_step.py
│
├── tests/                       # Pytest tests
│   └── engine/                  # Engine tests
│
├── requirements.txt
├── .env                         # Environment variables
├── CLAUDE.md                    # Este arquivo - Documentação completa
└── verify_features.py           # Script de verificação
```

---

## Modelo de Dados Principal

```
Organization
    │
    ├── User[]
    ├── AuditEvent[]  # v2.0 - Audit trail
    │
    ├── Workflow[]
    │       ├── WorkflowNode[]
    │       │
    │       └── WorkflowExecution[]  # v2.0 - Run State completo
    │               ├── ExecutionStep[]  # v2.0 - Error contexts
    │               ├── ExecutionLog[]  # v2.0 - Logs estruturados
    │               ├── WorkflowApproval[]
    │               └── SignatureRequest[]
    │
    ├── DataSourceConnection[]
    ├── Template[]
    └── GeneratedDocument[]
```

### Models Principais

| Model | Arquivo | Status | Descrição |
|-------|---------|--------|-----------|
| `Organization` | `models/organization.py` | ✅ | Tenant (multi-tenant) |
| `User` | `models/user.py` | ✅ | Usuários |
| `Workflow` | `models/workflow.py` | ✅ | Definição do workflow |
| `WorkflowNode` | `models/workflow.py` | ✅ | Nodes do workflow |
| `WorkflowExecution` | `models/execution.py` | ✅ v2.0 | Execução com Run State |
| `ExecutionStep` | `models/execution_step.py` | ✅ v2.0 | Steps com error contexts |
| `ExecutionLog` | `models/execution_log.py` | ✅ NEW | Logs estruturados |
| `AuditEvent` | `models/audit_event.py` | ✅ NEW | Audit trail append-only |
| `DataSourceConnection` | `models/connection.py` | ✅ | Conexões OAuth/API Key |
| `Template` | `models/template.py` | ✅ | Templates de documento |
| `GeneratedDocument` | `models/document.py` | ✅ | Documento gerado |
| `WorkflowApproval` | `models/approval.py` | ✅ | Aprovações pendentes |
| `SignatureRequest` | `models/signature.py` | ✅ | Requisições de assinatura |
| `WorkflowDatastore` | `models/datastore.py` | ✅ | Key-value persistente |

---

## Execução v2.0: Features Implementadas

> ✅ **Status:** 14/14 features implementadas e testadas
> 📅 **Data:** 23 de Dezembro de 2025

### F1: Run State Unificado ✅

**Fonte única de verdade para UI.**

#### ExecutionStatus (12 estados)

```python
class ExecutionStatus(str, Enum):
    QUEUED = 'queued'              # Na fila
    RUNNING = 'running'            # Executando
    NEEDS_REVIEW = 'needs_review'  # Preflight bloqueado
    READY = 'ready'                # Pronto para delivery
    SENDING = 'sending'            # Enviando documento
    SENT = 'sent'                  # Documento enviado
    SIGNING = 'signing'            # Aguardando assinaturas
    SIGNED = 'signed'              # Todas assinaturas coletadas
    COMPLETED = 'completed'        # Finalizado com sucesso
    FAILED = 'failed'              # Falhou
    CANCELED = 'canceled'          # Cancelado pelo usuário
    PAUSED = 'paused'              # Pausado (aguardando signal)
```

#### Novos Campos em WorkflowExecution

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `progress` | INTEGER | 0-100 (progresso visual) |
| `current_step` | JSONB | `{index, label, node_id, node_type}` |
| `last_error_human` | TEXT | Mensagem para usuário |
| `last_error_tech` | TEXT | Stack trace/detalhes técnicos |
| `preflight_summary` | JSONB | Resultado do preflight |
| `delivery_state` | VARCHAR(20) | Estado da entrega |
| `signature_state` | VARCHAR(20) | Estado das assinaturas |
| `recommended_actions` | JSONB | CTAs para resolver issues |
| `phase_metrics` | JSONB | Timing por fase |
| `correlation_id` | UUID | Rastreamento distribuído |

#### Métodos Helper

```python
execution.update_progress(45)
execution.update_current_step(2, "Gerando documento", node_id, "google-docs")
execution.set_error("Não foi possível acessar o template", "TemplateNotFoundError: ...")
execution.update_preflight_summary(blocking=[], warnings=[])
execution.set_recommended_actions([...])
execution.start_phase('render')
execution.complete_phase('render')
```

### F2: Preflight Validation ✅

**Validação ANTES de executar o workflow.**

#### Validações Implementadas

| Domínio | Validações |
|---------|------------|
| `data` | Campos required, variáveis resolvem |
| `template` | Arquivo existe, acessível |
| `permissions` | OAuth válido, acesso a recursos |
| `delivery` | Email válido, pasta destino existe |
| `signature` | Conexão ativa, signers válidos |

#### PreflightResult

```python
@dataclass
class PreflightResult:
    blocking: List[PreflightIssue]      # Impedem execução
    warnings: List[PreflightIssue]      # Não bloqueiam
    recommended_actions: List[RecommendedAction]  # CTAs
    groups: Dict[str, List[PreflightIssue]]  # Agrupados por domínio
```

#### Endpoints

```bash
# Executar preflight sem criar execução
POST /api/v1/workflows/{id}/preflight
{
  "trigger_data": {"deal_id": "123"}
}

# Ver resultado do preflight de uma execução
GET /api/v1/executions/{id}/preflight
```

### F3: SSE Schema v1 Padronizado ✅

**Schema de eventos real-time padronizado.**

#### Schema

```json
{
  "schema_version": 1,
  "event_id": "uuid",
  "event_type": "step.completed",
  "timestamp": "2025-12-23T10:30:00.000Z",
  "execution_id": "uuid",
  "workflow_id": "uuid",
  "organization_id": "uuid",
  "status": "running",
  "progress": 45,
  "current_step": {
    "index": 2,
    "label": "Generate Document",
    "node_id": "uuid"
  },
  "data": {
    "step_id": "uuid",
    "document_id": "uuid"
  }
}
```

#### Tipos de Eventos

**Execução:**
- `execution.created`
- `execution.status_changed`
- `execution.progress`
- `preflight.completed`
- `execution.completed`
- `execution.failed`
- `execution.canceled`

**Steps:**
- `step.started`
- `step.completed`
- `step.failed`

**Signatures (v2.0):**
- `signature.requested`
- `signature.completed`

**Signatures Granulares (v2.2):**
- `signature.signer.viewed` - Signatário visualizou documento
- `signature.signer.signed` - Signatário assinou
- `signature.signer.declined` - Signatário recusou
- `signature.expired` - Documento expirou
- `signature.completed` - Todos signatários assinaram

### F4: SSE com Replay (Redis Streams) ✅

**Eventos persistidos com capacidade de replay.**

#### Tecnologia

- **Redis Streams** (XADD, XREAD)
- **Persistência:** Últimos 1000 eventos
- **TTL:** 24 horas
- **Replay:** Via header `Last-Event-ID`

#### Como Usar

```bash
# Conectar ao stream
curl -N -H "Authorization: Bearer $TOKEN" \
  http://localhost:5000/api/v1/sse/executions/{id}/stream

# Reconectar com replay
curl -N -H "Authorization: Bearer $TOKEN" \
  -H "Last-Event-ID: 1234567890-0" \
  http://localhost:5000/api/v1/sse/executions/{id}/stream
```

#### Como Funciona o Replay

1. Cliente desconecta no evento `1234567890-0`
2. Cliente reconecta com header `Last-Event-ID: 1234567890-0`
3. Servidor envia todos eventos **após** esse ID do Redis Stream
4. Cliente recebe eventos perdidos, depois continua real-time

### F5: Logs Estruturados ✅

**Logs consultáveis e filtráveis.**

#### ExecutionLog Model

```python
class ExecutionLog(db.Model):
    id: UUID
    execution_id: UUID
    step_id: UUID (nullable)
    timestamp: DateTime
    level: str  # ok, warn, error
    domain: str  # preflight, step, delivery, signature
    message_human: str  # Para usuário
    details_tech: str  # Stack trace/detalhes
    correlation_id: UUID
```

#### ExecutionLogger Service

```python
logger = ExecutionLogger(execution_id, correlation_id)

logger.ok('step', 'Documento gerado com sucesso')
logger.warn('preflight', 'Template maior que 10MB', 'Template size: 15MB')
logger.error('delivery', 'Falha ao enviar email', 'SMTPException: ...')
```

#### Endpoint

```bash
GET /api/v1/executions/{id}/logs?level=error&domain=step&limit=50&cursor=uuid
```

**Query Parameters:**
- `level` - Filtrar por nível: `ok`, `warn`, `error`
- `domain` - Filtrar por domínio: `preflight`, `step`, `delivery`, `signature`
- `step_id` - Filtrar por step específico
- `limit` - Resultados por página (max: 100)
- `cursor` - UUID para paginação

### F6: Auditoria Append-Only ✅

**Trail imutável para compliance (nunca UPDATE/DELETE).**

#### AuditEvent Model

```python
class AuditEvent(db.Model):
    id: UUID
    organization_id: UUID
    timestamp: DateTime
    actor_type: str  # user, system, webhook
    actor_id: str
    action: str  # execution.started, document.generated, etc
    target_type: str  # execution, document, signature
    target_id: UUID
    event_metadata: JSONB  # 'metadata' é reservado no SQLAlchemy
```

#### Ações Auditadas

| Categoria | Ações |
|-----------|-------|
| **Executions** | started, completed, failed, canceled, retried, resumed |
| **Documents** | generated, saved, sent |
| **Signatures** | requested, signed, declined, expired |
| **Templates** | version_updated |

#### AuditService

```python
from app.services.audit_service import AuditService

AuditService.log(
    organization_id=org_id,
    action='execution.started',
    target_type='execution',
    target_id=execution_id,
    actor_type='user',
    actor_id=user_email,
    metadata={'workflow_name': 'Contract Gen'}
)
```

#### Endpoint

```bash
GET /api/v1/executions/{id}/audit?limit=50&cursor=uuid
```

### F7: Error Contexts ✅

**Erros separados para usuário e desenvolvedor.**

#### Campos em ExecutionStep

- `error_human` (TEXT) - Mensagem amigável para usuário
- `error_tech` (TEXT) - Stack trace e detalhes técnicos

#### Exemplo

```python
step.fail(
    error_details="Template not found",
    error_human="Não foi possível gerar o documento. Verifique se o template existe.",
    error_tech="TemplateNotFoundError: Template ID 'abc123' not found\n" + traceback
)
```

#### Endpoint

```bash
GET /api/v1/executions/{id}/steps
```

**Response:**
```json
{
  "steps": [
    {
      "id": "uuid",
      "status": "failure",
      "error_human": "Não foi possível gerar o documento...",
      "error_tech": "TemplateNotFoundError: ...\nTraceback:\n...",
      "data_in": {...},
      "data_out": null
    }
  ]
}
```

### F10: Pause/Resume/Cancel/Retry ✅

**Controle total da execução via Temporal signals.**

#### Novos Signals no DocGWorkflow

```python
@workflow.signal(name='resume_after_review')
async def resume_after_review_signal(data: Dict):
    """Retomar após needs_review (preflight fix)"""
    self._resume_requested = True
    self._resume_data = data

@workflow.signal(name='cancel')
async def cancel_signal(data: Dict):
    """Cancelar execução gracefully"""
    self._cancel_requested = True
    self._cancel_reason = data.get('reason')
```

#### Endpoints

```bash
# Retomar após needs_review
POST /api/v1/executions/{id}/resume
{
  "approved": true,
  "changes": {"recipient_email": "new@example.com"}
}

# Cancelar execução
POST /api/v1/executions/{id}/cancel
{
  "reason": "User requested cancellation"
}

# Retry (cria nova execução)
POST /api/v1/executions/{id}/retry
{
  "trigger_data": {...},
  "from_step": 3  # Opcional
}
```

### F12: Endpoints Adicionais ✅

**10 novos endpoints para gerenciamento de execuções.**

Todos os endpoints documentados estão implementados e funcionais. Ver seção [API REST](#api-rest-principal).

### F13: Recommended Actions ✅

**CTAs automáticas para resolver issues.**

#### RecommendedActionsService

```python
from app.services.recommended_actions import get_recommended_actions

actions = get_recommended_actions(preflight_issues)
# [
#   RecommendedAction(
#     action='fix_permissions',
#     label='Corrigir permissões',
#     description='Conceda acesso de leitura ao arquivo',
#     ...
#   )
# ]
```

#### Mapeamentos

| Código de Erro | Action | Label |
|----------------|--------|-------|
| `drive.insufficient_permissions` | `fix_permissions` | Corrigir permissões |
| `oauth_expired` | `reconnect_provider` | Reconectar |
| `rate_limit` | `retry_later` | Tentar novamente |
| `unresolved_variables` | `map_fields` | Mapear campos |
| `template.not_found` | `select_template` | Escolher template |

### F14: Observabilidade (Correlation ID + Phase Metrics) ✅

**Rastreamento distribuído e métricas de performance.**

#### Correlation ID

- Gerado na criação da execução (`uuid.uuid4()`)
- Propagado em:
  - Logs estruturados (`ExecutionLog.correlation_id`)
  - Eventos SSE (`event.correlation_id`)
  - Audit trail (`metadata.correlation_id`)
  - HTTP requests externos (header `X-Correlation-ID`)

#### Phase Metrics

```python
phase_metrics = {
    "preflight": {
        "started_at": "2025-12-23T10:30:00.000Z",
        "completed_at": "2025-12-23T10:30:00.234Z",
        "duration_ms": 234
    },
    "trigger": {"duration_ms": 567},
    "render": {"duration_ms": 3456},
    "delivery": {"duration_ms": 890}
}
```

**Usage:**
```python
execution.start_phase('render')
# ... processing ...
execution.complete_phase('render')  # Calcula duration_ms automaticamente
```

---

## Sistema de Tags Avançadas

> **Versão:** 1.0
> **Status:** ✅ Implementado

Sistema de processamento de tags inspirado no Docmergy e Portant, com sintaxe de pipes, fórmulas matemáticas, condicionais e loops.

### Sintaxe Suportada

#### Pipes/Transforms

```
{{trigger.deal.closedate | format:"DD/MM/YYYY"}}
{{trigger.deal.amount | currency:"BRL"}}
{{trigger.contact.firstname | upper}}
{{trigger.contact.email | lower}}
{{trigger.deal.description | truncate:100}}
```

#### Fórmulas Matemáticas

```
{{= trigger.deal.amount * 1.1}}
{{= ROUND(trigger.deal.amount, 2)}}
{{= SUM(trigger.deal.line_items.amount)}}
{{= IF(trigger.deal.amount > 10000, "Enterprise", "Standard")}}
```

#### Condicionais em Bloco

```
{{IF trigger.deal.amount > 50000}}
Você se qualifica para desconto de 10%!
{{ELSE}}
Entre em contato para negociar descontos.
{{ENDIF}}
```

#### Loops

```
{{FOR item IN trigger.deal.line_items}}
- {{item.name}}: {{item.quantity}} x {{item.price | currency:"BRL"}}
{{ENDFOR}}
```

#### Variáveis Globais

```
{{$timestamp}}           # ISO timestamp da geração
{{$date}}                # Data atual YYYY-MM-DD
{{$date_br}}             # Data atual DD/MM/YYYY
{{$time}}                # Hora atual HH:MM
{{$uuid}}                # UUID aleatório
{{$workflow_name}}       # Nome do workflow
```

### Transforms Disponíveis

| Categoria | Transforms |
|-----------|------------|
| **Texto** | `upper`, `lower`, `capitalize`, `truncate`, `concat`, `trim`, `replace`, `default` |
| **Data** | `format` (com locale pt-BR/en-US), `add_days`, `add_months`, `relative` |
| **Número** | `currency` (BRL, USD, EUR), `number`, `round`, `percent` |

### Funções para Fórmulas

`SUM`, `AVG`, `MIN`, `MAX`, `ROUND`, `ABS`, `IF`, `CONCAT`, `LEN`, `NOW`, `TODAY`

### Uso no Código

```python
# Modo básico (retrocompatível)
from app.engine.compute_parameters import compute_parameters
result = compute_parameters(params, trigger_output=data)

# Modo avançado (com pipes, fórmulas, etc)
result = compute_parameters(
    params,
    trigger_output=data,
    use_advanced_tags=True,
    trigger_source='hubspot',
    locale='pt_BR'
)

# Auto-detecção (detecta sintaxe avançada automaticamente)
from app.engine.compute_parameters import detect_and_compute
result = detect_and_compute(params, trigger_output=data)
```

### Preview de Tags

**Endpoint:** `POST /api/v1/workflows/{id}/tags/preview`

**Request:**
```json
{
  "object_type": "deal",
  "object_id": "123456",
  "template_content": "Valor: {{trigger.deal.amount | currency:\"BRL\"}}"
}
```

**Response:**
```json
{
  "tags": [
    {"tag": "{{trigger.deal.amount | currency:\"BRL\"}}", "resolved": "R$ 50.000,00", "status": "ok"}
  ],
  "loops": [],
  "conditionals": [],
  "warnings": [],
  "errors": [],
  "sample_output": "Valor: R$ 50.000,00",
  "stats": {"total_tags": 1, "resolved": 1, "warnings": 0, "errors": 0}
}
```

### Multi-CRM Normalizers

| Normalizer | Fonte | Associações |
|------------|-------|-------------|
| `HubSpotNormalizer` | HubSpot CRM | ✅ Sim |
| `WebhookNormalizer` | Webhook genérico | ❌ Não |
| `GoogleFormsNormalizer` | Google Forms | ❌ Não |
| `StripeNormalizer` | Stripe webhooks | ⚠️ Parcial |

### Segurança

- **Fórmulas:** AST parsing seguro (NÃO usa `eval()`)
- **Loops:** Limite de 1000 iterações
- **Recursão:** Máximo 3 níveis de loops aninhados

---

## HubSpot Expandido

> **Versão:** 1.0
> **Status:** ✅ Implementado
> **OAuth Scopes Adicionais:** `tickets`, `e-commerce`

### Actions de Tickets

| Action | Descrição |
|--------|-----------|
| `create-ticket` | Cria novo ticket |
| `update-ticket` | Atualiza ticket existente |
| `get-ticket` | Busca dados de um ticket |

**Exemplo - Criar Ticket:**
```json
{
  "subject": "Suporte técnico",
  "content": "Descrição do problema",
  "priority": "HIGH",
  "pipeline_stage": "1"
}
```

### Actions de Line Items

| Action | Descrição |
|--------|-----------|
| `get-line-items` | Busca line items de um deal |
| `create-line-item` | Cria line item (opcionalmente associado a deal) |

**Exemplo - Buscar Line Items:**
```json
{
  "deal_id": "123456"
}
```

**Response:**
```json
{
  "deal_id": "123456",
  "line_items": [
    {
      "id": "789",
      "name": "Produto A",
      "price": 100.00,
      "quantity": 2,
      "amount": 200.00
    }
  ],
  "count": 1,
  "total_amount": 200.00
}
```

### Sistema de Associações

Helper para buscar objetos relacionados no HubSpot:

```python
from app.apps.hubspot.common import AssociationsHelper

helper = AssociationsHelper(http_client)

# Buscar contatos de um deal
contacts = await helper.get_associated_objects('deal', deal_id, 'contact')

# Buscar company de um deal
company = await helper.get_first_associated_object('deal', deal_id, 'company')

# Buscar line items de um deal
line_items = await helper.get_associated_objects('deal', deal_id, 'line_item')
```

**Funções Helper:**
```python
from app.apps.hubspot.common import (
    get_deal_contacts,
    get_deal_company,
    get_deal_line_items,
    get_contact_company,
    get_contact_deals,
)
```

### OAuth Scopes

```python
# IMPORTANTE: Usar scopes corretos!

# Tickets - NÃO usar crm.objects.tickets
✅ CORRETO: 'tickets'
❌ ERRADO: 'crm.objects.tickets.read'

# Line Items - NÃO usar crm.objects.line_items
✅ CORRETO: 'e-commerce'
❌ ERRADO: 'crm.objects.line_items.read'
```

### Associações Disponíveis

| Objeto | Associações |
|--------|-------------|
| Contact | companies, deals |
| Deal | contacts, companies, line_items |
| Company | contacts, deals, tickets |
| Ticket | contacts, companies |

---

## API REST Principal

### Base URL

```
/api/v1
```

### Autenticação

```
Authorization: Bearer <JWT>
X-Organization-ID: <uuid>
```

### Endpoints - Executions v2.0 (NOVOS)

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| **Logs Estruturados** | | |
| GET | `/executions/{id}/logs` | Logs filtráveis (level, domain, step) |
| **Audit Trail** | | |
| GET | `/executions/{id}/audit` | Eventos de auditoria |
| **Steps Detalhados** | | |
| GET | `/executions/{id}/steps` | Steps com snapshots e erros |
| **Preflight** | | |
| POST | `/workflows/{id}/preflight` | Executar preflight validation |
| GET | `/executions/{id}/preflight` | Ver resultado do preflight |
| **Controle de Execução** | | |
| POST | `/executions/{id}/resume` | Retomar após needs_review |
| POST | `/executions/{id}/cancel` | Cancelar execução |
| POST | `/executions/{id}/retry` | Criar nova execução (retry, **+ dry_run/until_phase v2.2**) |
| **Tags Preview (v2.1)** | | |
| POST | `/workflows/{id}/tags/preview` | Preview de resolução de tags |
| POST | `/workflows/{id}/tags/validate` | Validar sintaxe de tags |
| **Signatures (v2.2)** | | |
| GET | `/signatures/{id}/signers` | Status detalhado de signatários |

### Endpoints - Workflows (Existentes)

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/workflows` | Listar workflows |
| POST | `/workflows` | Criar workflow |
| GET | `/workflows/{id}` | Detalhe do workflow |
| PUT | `/workflows/{id}` | Atualizar workflow |
| DELETE | `/workflows/{id}` | Deletar workflow |
| POST | `/workflows/{id}/activate` | Ativar workflow |
| POST | `/workflows/{id}/executions` | **Iniciar execução** |
| GET | `/workflows/{id}/runs` | Listar execuções do workflow |
| GET | `/executions/{id}` | **Detalhe da execução (+ Run State)** |

### Response Exemplo: GET /executions/{id}

```json
{
  "id": "uuid",
  "workflow_id": "uuid",
  "status": "running",
  "progress": 45,
  "current_step": {
    "index": 2,
    "label": "Gerando documento",
    "node_id": "uuid",
    "node_type": "google-docs"
  },
  "last_error_human": null,
  "last_error_tech": null,
  "preflight_summary": {
    "blocking_count": 0,
    "warning_count": 1,
    "groups": {
      "template": [{
        "code": "template.large_file",
        "severity": "warning",
        "message_human": "Template maior que 10MB pode demorar"
      }]
    }
  },
  "delivery_state": null,
  "signature_state": "signing",
  "recommended_actions": [],
  "phase_metrics": {
    "preflight": {"duration_ms": 234},
    "trigger": {"duration_ms": 567}
  },
  "correlation_id": "uuid",
  "started_at": "2025-12-23T10:30:00.000Z",
  "completed_at": null,
  "created_at": "2025-12-23T10:29:55.000Z",
  "updated_at": "2025-12-23T10:30:10.000Z"
}
```

---

## SSE (Server-Sent Events)

### Endpoint

```
GET /api/v1/sse/executions/{execution_id}/stream
```

### Headers

```
Authorization: Bearer <JWT>
X-Organization-ID: <uuid>
Last-Event-ID: <redis_event_id>  # Opcional, para replay
```

### Conectar com cURL

```bash
curl -N \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Organization-ID: $ORG_ID" \
  http://localhost:5000/api/v1/sse/executions/{id}/stream
```

### Reconectar com Replay

```bash
curl -N \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Organization-ID: $ORG_ID" \
  -H "Last-Event-ID: 1234567890-0" \
  http://localhost:5000/api/v1/sse/executions/{id}/stream
```

### EventSource (JavaScript)

```javascript
const eventSource = new EventSource(
  `/api/v1/sse/executions/${executionId}/stream`,
  {
    headers: {
      'Authorization': `Bearer ${token}`,
      'X-Organization-ID': orgId
    }
  }
);

eventSource.addEventListener('step.completed', (event) => {
  const data = JSON.parse(event.data);
  console.log('Step completed:', data);
  // Atualizar UI com data.progress, data.current_step
});

eventSource.addEventListener('execution.completed', (event) => {
  console.log('Execution completed!');
  eventSource.close();
});

// Replay automático ao reconectar
// O browser envia Last-Event-ID automaticamente
```

### Health Check

```bash
curl http://localhost:5000/api/v1/sse/health

# Response:
{
  "status": "healthy",
  "redis": "connected",
  "mode": "streams"
}
```

---

## Variáveis de Ambiente

```bash
# =============================================================================
# Database
# =============================================================================
DATABASE_URL=postgresql://user:pass@host:5432/docg_db

# =============================================================================
# Redis (Streams para SSE)
# =============================================================================
REDIS_URL=redis://localhost:6379/0
REDIS_STREAM_MAXLEN=1000      # Últimos N eventos por stream
REDIS_STREAM_TTL=86400        # TTL de streams em segundos (24h)

# =============================================================================
# Temporal - Workflow Orchestration
# =============================================================================
TEMPORAL_ADDRESS=localhost:7233
TEMPORAL_NAMESPACE=default
TEMPORAL_TASK_QUEUE=docg-workflows

# Task Queues especializadas
TEMPORAL_EMAIL_QUEUE=docg-emails
TEMPORAL_DOCUMENT_QUEUE=docg-documents
TEMPORAL_SIGNATURE_QUEUE=docg-signatures
TEMPORAL_WEBHOOK_QUEUE=docg-webhooks
TEMPORAL_APPROVAL_QUEUE=docg-approvals

# =============================================================================
# Security
# =============================================================================
SECRET_KEY=your-secret-key-here
BACKEND_API_TOKEN=your-api-token
ENCRYPTION_KEY=your-encryption-key  # AES-256 para credentials

# =============================================================================
# OAuth Providers
# =============================================================================
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
MICROSOFT_CLIENT_ID=...
MICROSOFT_CLIENT_SECRET=...
HUBSPOT_CLIENT_ID=...
HUBSPOT_CLIENT_SECRET=...

# =============================================================================
# Storage (DigitalOcean Spaces / S3-compatible)
# =============================================================================
DO_SPACES_ACCESS_KEY=...
DO_SPACES_SECRET_KEY=...
DO_SPACES_BUCKET=pipehub
DO_SPACES_ENDPOINT=https://nyc3.digitaloceanspaces.com

# =============================================================================
# Payments (Stripe)
# =============================================================================
STRIPE_SECRET_KEY=sk_...
STRIPE_WEBHOOK_SECRET=whsec_...

# =============================================================================
# Flask
# =============================================================================
FLASK_ENV=development
FRONTEND_URL=http://localhost:5173
```

---

## Comandos Úteis

### Setup Inicial

```bash
# Criar virtualenv
python -m venv venv
source venv/bin/activate

# Instalar dependências
pip install -r requirements.txt

# Copiar .env.example
cp .env.example .env
# Editar .env com suas credenciais
```

### Migrações

```bash
# Aplicar todas as migrations
flask db upgrade

# Criar nova migration
flask db migrate -m "Add new field"

# Reverter última migration
flask db downgrade

# Ver histórico de migrations
flask db history

# Ver status atual
flask db current
```

### Servidor

```bash
# Desenvolvimento (localhost:5000)
flask run

# Com auto-reload
flask run --reload

# Porta customizada
flask run --port 8000
```

### Temporal Worker

```bash
# Worker principal
python -m app.temporal.worker

# Worker em background
nohup python -m app.temporal.worker > worker.log 2>&1 &
```

### Testes

```bash
# Todos os testes
pytest

# Testes da engine
pytest tests/engine/ -v

# Com coverage
pytest --cov=app tests/

# Teste específico
pytest tests/engine/test_branching.py -v
```

### Redis

```bash
# Verificar streams
redis-cli XINFO STREAM docg:exec:{execution_id}

# Ver últimos eventos
redis-cli XREAD COUNT 10 STREAMS docg:exec:{execution_id} 0

# Limpar stream
redis-cli DEL docg:exec:{execution_id}
```

---

## ⚠️ Erros Comuns e Soluções

### 1. SQLAlchemy: "Attribute name 'metadata' is reserved"

**Erro:**
```
sqlalchemy.exc.InvalidRequestError: Attribute name 'metadata' is reserved
when using the Declarative API
```

**Causa:** `metadata` é palavra reservada do SQLAlchemy Declarative API.

**Solução:**

```python
# ❌ ERRADO
class MyModel(db.Model):
    metadata = db.Column(JSONB)

# ✅ CORRETO
class MyModel(db.Model):
    event_metadata = db.Column(JSONB)

    def to_dict(self):
        return {
            'metadata': self.event_metadata  # API mantém nome original
        }
```

**Outras palavras reservadas:**
- `metadata` ⚠️
- `query` ⚠️
- `mapper` ⚠️
- `session` ⚠️
- `c` ⚠️ (usado em consultas)

### 2. Redis Connection Error

**Erro:**
```
redis.exceptions.ConnectionError: Error connecting to Redis
```

**Solução:**

```bash
# Verificar se Redis está rodando
redis-cli ping
# Esperado: PONG

# Verificar URL no .env
echo $REDIS_URL

# Iniciar Redis (macOS)
brew services start redis

# Iniciar Redis (Linux)
sudo systemctl start redis

# Docker
docker run -d -p 6379:6379 redis:latest
```

### 3. Temporal Worker Não Conecta

**Erro:**
```
TemporalConnectionError: Cannot connect to Temporal server
```

**Solução:**

```bash
# Verificar se Temporal está rodando
curl http://localhost:7233

# Iniciar Temporal (Docker)
docker run -d -p 7233:7233 temporalio/auto-setup:latest

# Verificar logs do worker
python -m app.temporal.worker
```

### 4. Migration Conflito

**Erro:**
```
alembic.util.exc.CommandError: Target database is not up to date
```

**Solução:**

```bash
# Ver estado atual
flask db current

# Ver histórico
flask db history

# Se houver conflito, fazer merge
flask db merge heads

# Aplicar
flask db upgrade
```

### 5. SSE Stream Não Funciona

**Sintomas:** Cliente conecta mas não recebe eventos

**Debugging:**

```bash
# 1. Verificar SSE health
curl http://localhost:5000/api/v1/sse/health

# 2. Verificar se Redis Stream existe
redis-cli EXISTS docg:exec:{execution_id}

# 3. Ver eventos no stream
redis-cli XREAD COUNT 10 STREAMS docg:exec:{execution_id} 0

# 4. Testar conexão SSE
curl -N http://localhost:5000/api/v1/sse/executions/{id}/stream
```

**Soluções:**
- Verificar `REDIS_URL` no .env
- Verificar se execution_id está correto
- Verificar autenticação (Bearer token + Organization ID)
- Verificar logs do Flask: `flask run --debug`

---

## Testes e Verificação

### Script de Verificação Automática

```bash
# Executar script de verificação
python verify_features.py
```

O script verifica:
- ✅ Variáveis de ambiente configuradas
- ✅ Database schema (tabelas e colunas)
- ✅ Redis conectado e Streams funcionando
- ✅ Models podem ser importados
- ✅ Flask app inicializa
- ✅ Endpoints registrados

### Testes Manuais

#### Teste Rápido de SSE

```bash
# Terminal 1: Iniciar Flask
flask run

# Terminal 2: Conectar ao SSE
curl -N -H "Authorization: Bearer $TOKEN" \
  http://localhost:5000/api/v1/sse/executions/{id}/stream

# Terminal 3: Criar execução
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"trigger_data": {...}}' \
  http://localhost:5000/api/v1/workflows/{id}/executions
```

#### Teste de Preflight

```bash
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"trigger_data": {"deal_id": "123"}}' \
  http://localhost:5000/api/v1/workflows/{id}/preflight
```

### Testes Automatizados

```bash
# Testes unitários
pytest tests/

# Testes da engine
pytest tests/engine/ -v

# Com coverage
pytest --cov=app tests/
```

---

## Database Migrations (v2.0)

| Migration | Features | Descrição |
|-----------|----------|-----------|
| `u1v2w3x4y5z6` | F1, F14 | Run State + Phase Metrics + Correlation ID |
| `v1w2x3y4z5a6` | F5 | Tabela `execution_logs` |
| `w2x3y4z5a6b7` | F6 | Tabela `audit_events` |
| `x3y4z5a6b7c8` | F7 | Campos `error_human` e `error_tech` em `execution_steps` |

**Status:** ✅ Todas aplicadas em 23/12/2025

```bash
# Verificar
flask db current

# Output esperado
# x3y4z5a6b7c8 (head)
```

---

## Arquitetura de Observabilidade

```
┌─────────────────────────────────────────────┐
│          Frontend (UI)                      │
│  ┌──────────────────────────────────────┐   │
│  │ EventSource (SSE Client)             │   │
│  │ - Auto-reconnect                     │   │
│  │ - Last-Event-ID replay               │   │
│  │ - Schema v1 events                   │   │
│  └──────────────────────────────────────┘   │
└──────────────┬──────────────────────────────┘
               │ Server-Sent Events
               ▼
┌──────────────────────────────────────────────┐
│      Redis Streams                           │
│  ┌────────────────────────────────────────┐  │
│  │ docg:exec:{execution_id}               │  │
│  │ - XADD (publish events)                │  │
│  │ - XREAD (consume + replay)             │  │
│  │ - MAXLEN=1000 (keep last 1k events)    │  │
│  │ - TTL=24h (auto-expire)                │  │
│  └────────────────────────────────────────┘  │
└──────────────┬───────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────┐
│      Temporal Workflow (DocGWorkflow)        │
│  ┌────────────────────────────────────────┐  │
│  │ Activities:                            │  │
│  │ - PreflightActivity ✅ NEW             │  │
│  │ - TriggerActivity                      │  │
│  │ - DocumentActivity                     │  │
│  │ - SignatureActivity                    │  │
│  │ - EmailActivity                        │  │
│  │                                        │  │
│  │ Signals:                               │  │
│  │ - approval_decision                    │  │
│  │ - signature_update                     │  │
│  │ - resume_after_review ✅ NEW           │  │
│  │ - cancel ✅ NEW                        │  │
│  └────────────────────────────────────────┘  │
└──────────────┬───────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────┐
│      PostgreSQL                              │
│  ┌────────────────────────────────────────┐  │
│  │ Tables:                                │  │
│  │ - workflow_executions (Run State) ✅   │  │
│  │ - execution_steps (+ error ctx) ✅     │  │
│  │ - execution_logs ✅ NEW                │  │
│  │ - audit_events ✅ NEW                  │  │
│  │ - workflows, workflow_nodes            │  │
│  │ - organizations, users                 │  │
│  │ - templates, documents                 │  │
│  └────────────────────────────────────────┘  │
└──────────────────────────────────────────────┘
```

---

## Status da Implementação

### ✅ Completo (14/14 features v2.0)

- [x] F1: Run State Unificado
- [x] F2: Preflight Validation
- [x] F3: SSE Schema v1
- [x] F4: SSE com Replay (Redis Streams)
- [x] F5: Logs Estruturados
- [x] F6: Auditoria Append-Only
- [x] F7: Error Contexts
- [x] F10: Pause/Resume/Cancel/Retry
- [x] F12: Endpoints Adicionais
- [x] F13: Recommended Actions
- [x] F14: Correlation ID + Phase Metrics

### ✅ Completo (v2.1 - Tags + HubSpot)

- [x] Sistema de Tags Avançadas (Pipes, Fórmulas, Condicionais, Loops)
- [x] Preview de Tags API
- [x] Multi-CRM Normalizers (HubSpot, Webhook, Forms, Stripe)
- [x] HubSpot Tickets (create, update, get)
- [x] HubSpot Line Items (get, create)
- [x] HubSpot Associations Helper

### ✅ Post-MVP (v2.2 - Implementado)

- [x] F9: Dry-run & Until Phase - Execução preview sem persistência
- [x] F11: Melhorias em Signatures - Eventos SSE granulares por signatário
- [x] F3: Loops em Google Docs - Duplicação de linhas de tabela para arrays

### 🔄 Post-MVP (Futuro)

- [ ] Redis Streams cleanup job
- [ ] Dashboard de métricas
- [ ] Triggers para Tickets (new-ticket, ticket-updated)
- [ ] Signature Reminders (Temporal activities)

---

## Features Post-MVP (v2.2)

### F9: Dry-run & Until Phase

Controle granular de execução para testes e desenvolvimento.

**Parâmetros:**

```python
await Engine.run(
    workflow_id='...',
    trigger_data={...},
    dry_run=True,           # Pula delivery/signature
    until_phase='render',   # Para após fase específica
)
```

**Fases Disponíveis:**
1. `preflight` - Validações pré-execução
2. `trigger` - Extração de dados
3. `render` - Geração de documentos
4. `save` - Persistência (Drive/Storage)
5. `delivery` - Envio de emails
6. `signature` - Coleta de assinaturas

**Arquivos:**
- `app/engine/phases.py` - Enum de fases
- `app/engine/engine.py` - Parâmetros dry_run/until_phase
- `app/engine/steps/iterate.py` - Lógica de detecção e parada

**Endpoint:**
```bash
POST /api/v1/executions/{id}/retry
{
  "dry_run": true,
  "until_phase": "render"
}
```

---

### F11: Melhorias em Signatures

Eventos SSE granulares para tracking individual de signatários.

**Novos Eventos SSE:**

| Evento | Quando | Payload |
|--------|--------|---------|
| `signature.signer.viewed` | Signatário visualizou | `{signer_email, signature_request_id}` |
| `signature.signer.signed` | Signatário assinou | `{signer_email, signed_at}` |
| `signature.signer.declined` | Signatário recusou | `{signer_email, reason}` |
| `signature.expired` | Documento expirou | `{signature_request_id, expires_at}` |
| `signature.completed` | Todos assinaram | `{all_signers[]}` |

**Endpoint de Status:**
```bash
GET /api/v1/signatures/{id}/signers
```

Retorna:
```json
{
  "signature_request_id": "uuid",
  "status": "pending",
  "all_signed": false,
  "signers": [
    {
      "email": "user@example.com",
      "status": "signed",
      "signed_at": "2025-12-23T10:30:00Z"
    }
  ]
}
```

**Arquivos:**
- `app/routes/webhooks.py` - Emissão de eventos SSE granulares
- `app/routes/signatures.py` - Endpoint /signers

---

### F3: Loops em Google Docs

Duplicação automática de linhas de tabela para arrays.

**Sintaxe:**
```
{{FOR item IN line_items}}
{{item.name}} - {{item.quantity}} x {{item.price}}
{{END FOR}}
```

**Exemplo:**

Template (linha de tabela):
```
| {{FOR item IN line_items}}{{item.name}}{{END FOR}} | {{FOR item IN line_items}}{{item.price}}{{END FOR}} |
```

Dados:
```json
{
  "line_items": [
    {"name": "Product A", "price": 100},
    {"name": "Product B", "price": 200}
  ]
}
```

Resultado: 2 linhas duplicadas na tabela.

**Arquivos:**
- `app/services/document_generation/loop_parser.py` - Parser de sintaxe
- `app/services/document_generation/table_loops.py` - Lógica de duplicação
- `app/apps/google_docs/actions/replace_tags.py` - Integração

**Uso:**

1. Adicione o loop em uma linha de tabela no Google Docs
2. Passe o array no `replacements`:
```python
{
  "line_items": [
    {"name": "Item 1", "price": "R$ 100"},
    {"name": "Item 2", "price": "R$ 200"}
  ]
}
```
3. A action `replace-tags` detecta e duplica automaticamente

---

## Arquivos Principais do Código

| Arquivo | Descrição |
|---------|-----------|
| `app/models/execution.py` | Run State - Estados de execução e métricas |
| `app/models/execution_log.py` | Logs estruturados consultáveis |
| `app/models/audit_event.py` | Audit trail append-only |
| `app/services/sse_publisher.py` | SSE Publisher com Redis Streams |
| `app/services/execution_logger.py` | Helper para logging estruturado |
| `app/services/audit_service.py` | Helper para auditoria |
| `app/temporal/activities/preflight.py` | Validação prévia de workflows |
| `app/temporal/workflows/docg_workflow.py` | Workflow principal com signals |
| `app/tags/__init__.py` | TagProcessor - Sistema de tags avançadas |
| `app/tags/parser/parser.py` | Parser de sintaxe de tags |
| `app/tags/engine/evaluator.py` | Avaliador de tags e fórmulas |
| `app/engine/compute_parameters.py` | Substituição de variáveis e tags |
| `app/apps/hubspot/common/associations.py` | Associações HubSpot |
| `app/engine/phases.py` | **[v2.2]** Enum de fases de execução |
| `app/services/document_generation/loop_parser.py` | **[v2.2]** Parser de loops para Google Docs |
| `app/services/document_generation/table_loops.py` | **[v2.2]** Duplicação de linhas de tabela |
| `verify_features.py` | Script de verificação de setup |

---

**Versão:** 2.2 - Post-MVP Features
**Status:** ✅ Production Ready
**Última Atualização:** 23 de Dezembro de 2025
**Migrations Aplicadas:** 4/4
**Features v2.0 Implementadas:** 14/14
**Features v2.1 Implementadas:** Tags Avançadas, HubSpot Tickets/Line Items/Associations
**Features v2.2 Implementadas:** Dry-run/Until Phase, Signature Events SSE, Loops Google Docs
