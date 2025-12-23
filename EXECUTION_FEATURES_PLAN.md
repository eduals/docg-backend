# Plano de Features: Execução de Workflows v2.0

> **Data:** 23 de Dezembro de 2025
> **Status:** Planejamento
> **Versão:** 1.0

---

## Resumo Executivo

Este documento detalha 13 features para evoluir a arquitetura de execução do DocG, focando em:
- **Observabilidade**: Run State completo, logs estruturados, auditoria
- **Realtime**: SSE com replay via Redis Streams
- **Resiliência**: Preflight, pause/resume, dry-run
- **Extensibilidade**: Arquitetura que suporta todos os apps atuais e futuros

---

## Análise do Estado Atual

### O Que Já Existe

| Componente | Status | Arquivos |
|------------|--------|----------|
| WorkflowExecution | Parcial | `app/models/execution.py` |
| ExecutionStep | Completo | `app/models/execution_step.py` |
| SSE Endpoint | Funcional | `app/routes/sse.py` |
| Redis Pub/Sub | Funcional | `app/services/sse_publisher.py` |
| Temporal Workflows | Completo | `app/temporal/workflows/docg_workflow.py` |
| Signals (approval/signature) | Completo | 2 signals implementados |
| Logging | Parcial | JSONB em `execution_logs` |
| Audit Trail | Não existe | - |

### Apps Disponíveis (14 apps)

| Categoria | Apps | Auth |
|-----------|------|------|
| **CRM** | HubSpot | OAuth2 |
| **Documentos** | Google Docs, Google Slides, Microsoft Word, Microsoft PowerPoint | OAuth2 |
| **Email** | Gmail, Outlook | OAuth2 |
| **Assinatura** | ClickSign, ZapSign | API Key |
| **Storage** | Google Drive, Storage (DO Spaces) | OAuth2 / API Key |
| **Triggers** | Google Forms | OAuth2 |
| **AI** | AI (OpenAI, Anthropic, Google) | API Key |
| **Pagamentos** | Stripe | Bearer Token |

**Total:** 36 actions, 4 triggers, 3 dynamic data providers, 4 webhooks

---

## Features a Implementar

### Feature 1 — Run State (Fonte de Verdade para UI)

**Objetivo:** Centralizar todo estado de execução em `WorkflowExecution` para a UI consumir.

#### 1.1 Novo Enum de Status

```python
# Status atual: running, paused, completed, failed

# Novo enum completo:
class ExecutionStatus(str, Enum):
    QUEUED = 'queued'           # Na fila, aguardando início
    RUNNING = 'running'         # Executando
    NEEDS_REVIEW = 'needs_review'  # Bloqueado por preflight/erro recuperável
    READY = 'ready'             # Preflight ok, pronto para continuar
    SENDING = 'sending'         # Enviando documento
    SENT = 'sent'               # Documento enviado
    SIGNING = 'signing'         # Aguardando assinaturas
    SIGNED = 'signed'           # Todas assinaturas coletadas
    COMPLETED = 'completed'     # Finalizado com sucesso (alias para sent/signed)
    FAILED = 'failed'           # Erro irrecuperável
    CANCELED = 'canceled'       # Cancelado pelo usuário
    PAUSED = 'paused'           # Pausado manualmente
```

#### 1.2 Novos Campos em WorkflowExecution

```python
# app/models/execution.py - Campos a adicionar

# Progresso
progress = db.Column(db.Integer, default=0)  # 0-100
current_step = db.Column(JSONB, nullable=True)
# {index: 2, label: "Gerando documento", node_id: "uuid", node_type: "google-docs"}

# Erros separados
last_error_human = db.Column(db.Text, nullable=True)   # "Não foi possível acessar o arquivo"
last_error_tech = db.Column(db.Text, nullable=True)    # "google.api.PermissionDenied: 403"

# Preflight
preflight_summary = db.Column(JSONB, nullable=True)
# {blocking_count: 2, warning_count: 1, completed_at: "ISO", groups: {...}}

# Estados de delivery/signature (agregados)
delivery_state = db.Column(db.String(20), nullable=True)   # pending, sending, sent, failed
signature_state = db.Column(db.String(20), nullable=True)  # pending, signing, signed, declined, expired

# Ações recomendadas
recommended_actions = db.Column(JSONB, nullable=True)
# [{action: "fix_permissions", target: "drive_folder", params: {...}}]
```

#### 1.3 Migration

```bash
# migrations/versions/xxx_add_run_state_fields.py
flask db migrate -m "Add run state fields to workflow_execution"
```

#### 1.4 Arquivos a Modificar

| Arquivo | Mudança |
|---------|---------|
| `app/models/execution.py` | Adicionar campos, enum |
| `app/serializers/execution_serializer.py` | Expor novos campos |
| `app/temporal/activities/base.py` | Atualizar campos durante execução |

---

### Feature 2 — Preflight Real

**Objetivo:** Validar tudo ANTES de executar, identificando bloqueios e avisos.

#### 2.1 PreflightActivity (Temporal)

```python
# app/temporal/activities/preflight.py (NOVO)

@dataclass
class PreflightResult:
    blocking: List[PreflightIssue]     # Impedem execução
    warnings: List[PreflightIssue]     # Não impedem, mas alertam
    recommended_actions: List[RecommendedAction]
    groups: Dict[str, List[PreflightIssue]]  # Por categoria

@dataclass
class PreflightIssue:
    code: str           # "drive.insufficient_permissions"
    domain: str         # "permissions", "data", "template", "delivery"
    message_human: str  # "Você não tem permissão para acessar a pasta de destino"
    message_tech: str   # "google.api.PermissionDenied on folder xyz"
    node_id: str        # Qual node causou
    severity: str       # "blocking" ou "warning"

@activity.defn
async def run_preflight(execution_id: str) -> PreflightResult:
    """
    Validações:
    1. Dados - Variáveis não resolvidas, campos obrigatórios
    2. Template - Arquivo existe, tags válidas
    3. Permissões - Acesso real ao Drive/OneDrive
    4. Entrega - Email válido, pasta destino existe
    5. Assinatura - Conexão ativa, signers válidos
    """
```

#### 2.2 Validações por Domínio

| Domínio | Validações |
|---------|------------|
| **data** | Variáveis `{{step.x.y}}` resolvem? Campos required preenchidos? |
| **template** | Arquivo existe? Tags `{{tag}}` mapeadas? |
| **permissions** | Acesso leitura ao template? Acesso escrita à pasta destino? |
| **delivery** | Email válido? Pasta destino existe? |
| **signature** | Conexão ativa? Signers com email válido? |

#### 2.3 Fluxo de Execução com Preflight

```
1. Inicia execução → status = 'running'
2. Executa PreflightActivity
3. Se blocking_count > 0:
   - status = 'needs_review'
   - recommended_actions = [...]
   - Aguarda signal 'resume_after_review'
4. Se ok → continua execução normal
```

#### 2.4 Arquivos a Criar/Modificar

| Arquivo | Ação |
|---------|------|
| `app/temporal/activities/preflight.py` | CRIAR |
| `app/temporal/workflows/docg_workflow.py` | Chamar preflight antes de actions |
| `app/models/execution.py` | Método `update_preflight_result()` |

---

### Feature 3 — SSE Realtime v1 (Schema Padronizado)

**Objetivo:** Padronizar eventos SSE com schema versionado.

#### 3.1 Schema v1

```python
# Estrutura base de todo evento
{
    "schema_version": 1,
    "event_id": "uuid",           # Para dedupe/replay
    "event_type": "step.completed",
    "timestamp": "2025-01-15T10:30:00.000Z",

    # Contexto sempre presente
    "execution_id": "uuid",
    "workflow_id": "uuid",
    "organization_id": "uuid",

    # Estado atual (snapshot)
    "status": "running",
    "progress": 45,
    "current_step": {
        "index": 2,
        "label": "Gerando documento",
        "node_id": "uuid",
        "node_type": "google-docs"
    },

    # Dados específicos do evento
    "data": { ... }
}
```

#### 3.2 Eventos SSE

| Evento | Quando | Data |
|--------|--------|------|
| `execution.created` | Execução criada | `trigger_type`, `trigger_data` |
| `execution.status_changed` | Status mudou | `from`, `to`, `reason` |
| `execution.progress` | Progresso atualizado | `progress`, `current_step` |
| `preflight.completed` | Preflight terminou | `blocking_count`, `warning_count`, `groups` |
| `step.started` | Step iniciou | `node_id`, `node_type`, `position` |
| `step.completed` | Step completou | `node_id`, `duration_ms`, `output_preview` |
| `step.failed` | Step falhou | `node_id`, `error_human`, `error_tech` |
| `execution.paused` | Pausou | `reason`, `waiting_for` |
| `execution.canceled` | Cancelado | `canceled_by`, `reason` |
| `execution.failed` | Falhou | `error_human`, `error_tech` |
| `signature.requested` | Assinatura solicitada | `envelope_id`, `signers` |
| `signature.completed` | Assinatura concluída | `envelope_id`, `signed_at` |

#### 3.3 Arquivos a Modificar

| Arquivo | Mudança |
|---------|---------|
| `app/services/sse_publisher.py` | Novo método `publish_v1()` com schema |
| `app/temporal/activities/base.py` | Emitir eventos no novo formato |
| `app/routes/sse.py` | Adicionar `schema_version` no output |

---

### Feature 4 — Replay de Eventos (Redis Streams)

**Objetivo:** Suportar reconexão com replay de eventos perdidos.

#### 4.1 Migrar Pub/Sub para Streams

```python
# Atual (Pub/Sub - sem persistência):
redis.publish(f"execution:{id}", message)

# Novo (Streams - com persistência):
redis.xadd(
    f"docg:exec:{id}",
    {"event": json.dumps(message)},
    maxlen=1000  # Últimos 1000 eventos
)
```

#### 4.2 SSE com Cursor

```python
# app/routes/sse.py

@bp.route('/executions/<execution_id>/stream')
def stream_execution(execution_id):
    # Suportar Last-Event-ID para replay
    last_id = request.headers.get('Last-Event-ID', '0')

    def generate():
        # Replay eventos perdidos
        events = redis.xread({f"docg:exec:{execution_id}": last_id})
        for event_id, data in events:
            yield f"id: {event_id}\nevent: {data['type']}\ndata: {data['payload']}\n\n"

        # Continuar streaming
        while True:
            events = redis.xread({f"docg:exec:{execution_id}": '$'}, block=5000)
            for event_id, data in events:
                yield f"id: {event_id}\nevent: {data['type']}\ndata: {data['payload']}\n\n"
```

#### 4.3 Retention

```python
# Reter eventos por 24h ou últimos 1000
STREAM_MAXLEN = 1000
STREAM_TTL = 86400  # 24h

# Cleanup job (cron)
def cleanup_old_streams():
    for key in redis.scan_iter("docg:exec:*"):
        redis.xtrim(key, maxlen=STREAM_MAXLEN)
```

#### 4.4 Arquivos a Modificar

| Arquivo | Mudança |
|---------|---------|
| `app/services/sse_publisher.py` | Usar XADD em vez de PUBLISH |
| `app/routes/sse.py` | Suportar Last-Event-ID, usar XREAD |
| `app/config.py` | Adicionar `REDIS_STREAM_MAXLEN`, `REDIS_STREAM_TTL` |

---

### Feature 5 — Logs Estruturados

**Objetivo:** Logs consultáveis com separação humano/técnico.

#### 5.1 Nova Tabela

```python
# app/models/execution_log.py (NOVO)

class ExecutionLog(db.Model):
    __tablename__ = 'execution_logs'

    id = db.Column(UUID, primary_key=True, default=uuid.uuid4)
    execution_id = db.Column(UUID, db.ForeignKey('workflow_executions.id'), nullable=False)
    step_id = db.Column(UUID, db.ForeignKey('execution_steps.id'), nullable=True)

    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    level = db.Column(db.String(10), nullable=False)  # ok, warn, error
    domain = db.Column(db.String(50), nullable=False)  # preflight, step, delivery, signature

    message_human = db.Column(db.Text, nullable=False)  # "Documento gerado com sucesso"
    details_tech = db.Column(db.Text, nullable=True)    # Stack trace, response body

    correlation_id = db.Column(UUID, nullable=False)  # Único por execução

    # Índices
    __table_args__ = (
        db.Index('ix_execution_logs_execution_id', 'execution_id'),
        db.Index('ix_execution_logs_level', 'level'),
        db.Index('ix_execution_logs_domain', 'domain'),
        db.Index('ix_execution_logs_correlation_id', 'correlation_id'),
    )
```

#### 5.2 Helper para Logging

```python
# app/services/execution_logger.py (NOVO)

class ExecutionLogger:
    def __init__(self, execution_id: str, correlation_id: str):
        self.execution_id = execution_id
        self.correlation_id = correlation_id

    def ok(self, domain: str, message_human: str, details_tech: str = None, step_id: str = None):
        self._log('ok', domain, message_human, details_tech, step_id)

    def warn(self, domain: str, message_human: str, details_tech: str = None, step_id: str = None):
        self._log('warn', domain, message_human, details_tech, step_id)

    def error(self, domain: str, message_human: str, details_tech: str = None, step_id: str = None):
        self._log('error', domain, message_human, details_tech, step_id)
```

#### 5.3 Endpoint

```
GET /api/v1/executions/{id}/logs?level=error&domain=step&cursor=xxx&limit=50
```

```python
# app/controllers/api/v1/executions/logs_controller.py (NOVO)

@bp.route('/<execution_id>/logs', methods=['GET'])
def get_logs(execution_id):
    level = request.args.get('level')
    domain = request.args.get('domain')
    cursor = request.args.get('cursor')
    limit = min(int(request.args.get('limit', 50)), 100)

    query = ExecutionLog.query.filter_by(execution_id=execution_id)
    if level:
        query = query.filter_by(level=level)
    if domain:
        query = query.filter_by(domain=domain)
    if cursor:
        query = query.filter(ExecutionLog.id > cursor)

    logs = query.order_by(ExecutionLog.timestamp).limit(limit).all()
    return jsonify({
        'logs': [log.to_dict() for log in logs],
        'next_cursor': str(logs[-1].id) if logs else None
    })
```

#### 5.4 Arquivos a Criar/Modificar

| Arquivo | Ação |
|---------|------|
| `app/models/execution_log.py` | CRIAR |
| `app/services/execution_logger.py` | CRIAR |
| `app/controllers/api/v1/executions/logs_controller.py` | CRIAR |
| `app/temporal/activities/base.py` | Usar ExecutionLogger |
| `migrations/versions/xxx_create_execution_logs.py` | CRIAR |

---

### Feature 6 — Auditoria Append-Only

**Objetivo:** Trail de auditoria imutável para compliance.

#### 6.1 Nova Tabela

```python
# app/models/audit_event.py (NOVO)

class AuditEvent(db.Model):
    __tablename__ = 'audit_events'

    id = db.Column(UUID, primary_key=True, default=uuid.uuid4)
    organization_id = db.Column(UUID, db.ForeignKey('organizations.id'), nullable=False)

    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    actor_type = db.Column(db.String(20), nullable=False)  # user, system, webhook
    actor_id = db.Column(db.String(255), nullable=True)    # user_id, "temporal", "stripe"

    action = db.Column(db.String(100), nullable=False)     # execution.started, document.generated
    target_type = db.Column(db.String(50), nullable=False) # execution, document, signature
    target_id = db.Column(UUID, nullable=False)

    metadata = db.Column(JSONB, nullable=True)  # Dados extras

    # Sem UPDATE, sem DELETE - append-only
    __table_args__ = (
        db.Index('ix_audit_events_org_target', 'organization_id', 'target_type', 'target_id'),
        db.Index('ix_audit_events_timestamp', 'timestamp'),
    )
```

#### 6.2 Ações a Auditar

| Ação | Quando |
|------|--------|
| `execution.started` | Execução iniciada |
| `execution.canceled` | Execução cancelada |
| `execution.retried` | Execução reexecutada |
| `execution.resumed` | Execução retomada após pausa |
| `document.generated` | Documento gerado |
| `document.saved` | Documento salvo no Drive |
| `document.sent` | Documento enviado por email |
| `signature.requested` | Assinatura solicitada |
| `signature.signed` | Documento assinado |
| `signature.declined` | Assinatura recusada |
| `signature.expired` | Assinatura expirou |
| `template.version_updated` | Template atualizado |

#### 6.3 Endpoint

```
GET /api/v1/executions/{id}/audit?cursor=xxx&limit=50
```

#### 6.4 Arquivos a Criar

| Arquivo | Ação |
|---------|------|
| `app/models/audit_event.py` | CRIAR |
| `app/services/audit_service.py` | CRIAR - helper para registrar eventos |
| `app/controllers/api/v1/executions/audit_controller.py` | CRIAR |
| `migrations/versions/xxx_create_audit_events.py` | CRIAR |

---

### Feature 7 — Steps Persistidos + Snapshots

**Objetivo:** Garantir que ExecutionStep tenha todos os dados necessários.

#### 7.1 Campos Existentes (já implementado)

```python
# app/models/execution_step.py - JÁ EXISTE
status          # pending, running, success, failure, skipped
started_at      # Quando iniciou
completed_at    # Quando finalizou
data_in         # Input snapshot (JSONB)
data_out        # Output snapshot (JSONB)
error_details   # Mensagem de erro
```

#### 7.2 Campos a Adicionar

```python
# Separar erro humano/técnico
error_human = db.Column(db.Text, nullable=True)  # "Não foi possível copiar o template"
error_tech = db.Column(db.Text, nullable=True)   # "google.api.404: File not found"

# Limpar data_in/data_out de PII
# Adicionar método para sanitizar
def sanitize_snapshot(self, data: dict) -> dict:
    """Remove campos sensíveis do snapshot"""
    sensitive_keys = ['password', 'token', 'secret', 'api_key', 'credentials']
    # ... implementação
```

#### 7.3 Endpoint

```
GET /api/v1/executions/{id}/steps
```

```python
# app/controllers/api/v1/executions/steps_controller.py (NOVO)

@bp.route('/<execution_id>/steps', methods=['GET'])
def get_steps(execution_id):
    steps = ExecutionStep.query.filter_by(
        execution_id=execution_id
    ).order_by(ExecutionStep.position).all()

    return jsonify({
        'steps': [step.to_dict() for step in steps]
    })
```

---

### Feature 9 — Dry-run e Until Phase

**Objetivo:** Execução parcial para preview e debug.

#### 9.1 Parâmetros

```python
# Engine.run() - parâmetros existentes
await Engine.run(
    workflow_id='...',
    trigger_data={...},
    test_run=True,          # Já existe
    until_step='node-uuid', # Já existe
    skip_steps=['node-1'],  # Já existe
    mock_data={...},        # Já existe

    # NOVOS:
    dry_run=True,           # Executa preflight + gera preview, nunca entrega/assina
    until_phase='render',   # Parar após fase específica
)
```

#### 9.2 Fases

| Fase | Descrição | Parar aqui significa |
|------|-----------|---------------------|
| `preflight` | Validações | Só valida, não executa nada |
| `trigger` | Extração de dados | Extrai dados do trigger |
| `render` | Geração de documento | Gera documento mas não salva/envia |
| `save` | Salva documento | Salva no Drive mas não envia |
| `delivery` | Envia por email | Envia mas não solicita assinatura |
| `signature` | Coleta assinaturas | Fluxo completo |

#### 9.3 Dry-run Behavior

```python
if dry_run:
    # Executa normalmente até render
    # Gera preview/artifact temporário
    # NUNCA chama DeliveryActivity ou SignatureActivity
    # Retorna preview_url e dados validados

    return DryRunResult(
        preflight_result=preflight,
        preview_url="https://...",
        render_output={...}
    )
```

---

### Feature 10 — Pause/Resume via Signals

**Objetivo:** Controle completo de pause/resume via Temporal Signals.

#### 10.1 Signals Existentes

```python
# JÁ IMPLEMENTADOS:
- approval_decision   # Recebe aprovação/rejeição
- signature_update    # Recebe status de assinatura
```

#### 10.2 Novos Signals

```python
# app/temporal/workflows/docg_workflow.py

# Novos signals a adicionar:
@workflow.signal
def resume_after_review(self, data: dict):
    """Retomar após needs_review (preflight fix)"""
    self._resume_requested = True
    self._resume_data = data

@workflow.signal
def cancel(self, data: dict):
    """Cancelar execução"""
    self._cancel_requested = True
    self._cancel_reason = data.get('reason', 'User requested')
```

#### 10.3 Fluxo needs_review

```
1. Preflight encontra blocking issues
2. status = 'needs_review'
3. recommended_actions = [{action: "fix_permissions", ...}]
4. Workflow aguarda signal 'resume_after_review'
5. Usuário corrige problema no frontend
6. Frontend envia signal via API
7. Workflow reexecuta preflight
8. Se ok → continua
```

#### 10.4 API para Signals

```python
# app/controllers/api/v1/executions/control_controller.py (NOVO)

@bp.route('/<execution_id>/resume', methods=['POST'])
def resume_execution(execution_id):
    """Enviar signal para retomar execução"""
    execution = WorkflowExecution.query.get_or_404(execution_id)

    if execution.status != 'needs_review':
        return jsonify({'error': 'Cannot resume - not in needs_review status'}), 400

    # Enviar signal para Temporal
    handle = temporal_client.get_workflow_handle(execution.temporal_workflow_id)
    await handle.signal('resume_after_review', request.json)

    return jsonify({'status': 'signal_sent'})

@bp.route('/<execution_id>/cancel', methods=['POST'])
def cancel_execution(execution_id):
    """Cancelar execução"""
    # Similar...
```

---

### Feature 11 — Signature como Fase Explícita

**Objetivo:** Tratar assinatura como fase com eventos próprios.

> **Nota:** Não controlamos delivery de email (apenas enviamos). Para assinaturas, recebemos webhooks das plataformas (ClickSign, ZapSign).

#### 11.1 SignatureActivity (já existe, melhorar)

```python
# app/temporal/activities/signature.py - MELHORIAS

@activity.defn
async def create_signature_request(execution_id: str, node_id: str) -> SignatureResult:
    # Já implementado, adicionar:
    # 1. Emitir evento SSE 'signature.requested'
    # 2. Atualizar execution.signature_state = 'signing'
    # 3. Registrar audit event
```

#### 11.2 Webhook Handler (já existe)

```python
# app/apps/clicksign/webhooks/signature_callback.py
# app/apps/zapsign/webhooks/signature_callback.py

# Já recebem webhooks das plataformas
# Adicionar:
# 1. Emitir evento SSE 'signature.completed' ou 'signature.declined'
# 2. Atualizar execution.signature_state
# 3. Enviar signal para Temporal workflow
```

#### 11.3 Eventos de Assinatura

| Evento SSE | Trigger |
|------------|---------|
| `signature.requested` | SignatureActivity cria envelope |
| `signature.sent` | Webhook confirma envio |
| `signature.viewed` | Webhook: signer abriu documento |
| `signature.signed` | Webhook: signer assinou |
| `signature.declined` | Webhook: signer recusou |
| `signature.completed` | Todos signers completaram |
| `signature.expired` | Prazo expirou |

---

### Feature 12 — Endpoints "HubSpot Friendly"

**Objetivo:** API previsível e rápida para integração.

#### 12.1 Endpoints a Implementar

| Método | Endpoint | Status | Descrição |
|--------|----------|--------|-----------|
| POST | `/workflows/{id}/executions` | Existe | Criar execução |
| GET | `/executions/{id}` | Existe | Run State completo |
| POST | `/workflows/{id}/preflight` | NOVO | Executar só preflight |
| GET | `/executions/{id}/preflight` | NOVO | Resultado do preflight |
| POST | `/executions/{id}/retry` | NOVO | Reexecutar |
| POST | `/executions/{id}/cancel` | NOVO | Cancelar |
| POST | `/executions/{id}/resume` | NOVO | Retomar após pause |
| POST | `/executions/{id}/request-signature` | NOVO | Iniciar assinatura manual |
| GET | `/executions/{id}/stream` | Existe | SSE |
| GET | `/executions/{id}/logs` | NOVO | Logs estruturados |
| GET | `/executions/{id}/audit` | NOVO | Audit trail |
| GET | `/executions/{id}/steps` | NOVO | Steps com snapshots |

#### 12.2 Response Padrão

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
    "preflight_summary": {
        "blocking_count": 0,
        "warning_count": 1
    },
    "delivery_state": null,
    "signature_state": "signing",
    "last_error_human": null,
    "last_error_tech": null,
    "recommended_actions": [],
    "started_at": "ISO",
    "completed_at": null
}
```

---

### Feature 13 — Recommended Actions (CTAs)

**Objetivo:** Backend gera CTAs específicas para cada erro.

#### 13.1 Mapeamento Erro → Ação

```python
# app/services/recommended_actions.py (NOVO)

ACTION_MAPPINGS = {
    # Permissões
    'drive.insufficient_permissions': {
        'action': 'fix_permissions',
        'label': 'Corrigir permissões',
        'description': 'Conceda acesso de leitura ao arquivo',
    },
    'drive.folder_not_found': {
        'action': 'select_folder',
        'label': 'Selecionar pasta',
        'description': 'A pasta de destino não existe mais',
    },

    # Dados
    'unresolved_variables': {
        'action': 'map_fields',
        'label': 'Mapear campos',
        'description': 'Algumas variáveis não foram resolvidas',
    },
    'missing_required_field': {
        'action': 'fill_required',
        'label': 'Preencher campos',
        'description': 'Campos obrigatórios estão vazios',
    },

    # Conexões
    'oauth_expired': {
        'action': 'reconnect_provider',
        'label': 'Reconectar',
        'description': 'A conexão expirou',
    },
    'connection_error': {
        'action': 'reconnect_provider',
        'label': 'Verificar conexão',
        'description': 'Erro ao conectar com o serviço',
    },

    # Transient
    'rate_limit': {
        'action': 'retry',
        'label': 'Tentar novamente',
        'description': 'Limite de requisições atingido',
    },
    'timeout': {
        'action': 'retry',
        'label': 'Tentar novamente',
        'description': 'Tempo limite excedido',
    },
}

def get_recommended_actions(issues: List[PreflightIssue]) -> List[RecommendedAction]:
    actions = []
    for issue in issues:
        if issue.code in ACTION_MAPPINGS:
            mapping = ACTION_MAPPINGS[issue.code]
            actions.append(RecommendedAction(
                action=mapping['action'],
                label=mapping['label'],
                description=mapping['description'],
                target_node_id=issue.node_id,
                params={'issue_code': issue.code}
            ))
    return actions
```

---

### Feature 14 — Observabilidade Mínima

**Objetivo:** Rastreabilidade e métricas básicas.

#### 14.1 Correlation ID

```python
# Gerado na criação da execução
correlation_id = uuid.uuid4()

# Propagado em:
# - Todos ExecutionLog
# - Todos eventos SSE
# - Headers de requests externos (X-Correlation-ID)
# - Logs estruturados
```

#### 14.2 Métricas por Fase

```python
# app/models/execution.py

phase_metrics = db.Column(JSONB, nullable=True)
# {
#     "preflight": {"started_at": "ISO", "completed_at": "ISO", "duration_ms": 234},
#     "trigger": {"started_at": "ISO", "completed_at": "ISO", "duration_ms": 567},
#     "render": {"started_at": "ISO", "completed_at": "ISO", "duration_ms": 3456},
#     "delivery": {"started_at": "ISO", "completed_at": "ISO", "duration_ms": 890},
#     "signature": {"started_at": "ISO", "completed_at": "ISO", "duration_ms": null}
# }
```

---

## Ordem de Implementação

| Fase | Features | Dependências | Esforço |
|------|----------|--------------|---------|
| **1** | F1 (Run State) | - | Médio |
| **2** | F5 (Logs), F6 (Audit) | F1 | Médio |
| **3** | F3 (SSE v1), F4 (Redis Streams) | F1 | Médio |
| **4** | F2 (Preflight), F13 (Actions) | F1, F5 | Alto |
| **5** | F10 (Pause/Resume) | F2 | Médio |
| **6** | F11 (Signature), F7 (Steps) | F1, F5 | Baixo |
| **7** | F9 (Dry-run), F12 (Endpoints) | Todas | Médio |
| **8** | F14 (Observability) | Todas | Baixo |

---

## Migrations Necessárias

```bash
# Ordem de criação

# 1. Run State fields
flask db migrate -m "Add run state fields"

# 2. Execution logs table
flask db migrate -m "Create execution_logs table"

# 3. Audit events table
flask db migrate -m "Create audit_events table"

# 4. Phase metrics
flask db migrate -m "Add phase_metrics to execution"

# 5. Error fields em ExecutionStep
flask db migrate -m "Add error_human error_tech to execution_step"
```

---

## Arquivos a Criar

| Arquivo | Feature |
|---------|---------|
| `app/models/execution_log.py` | F5 |
| `app/models/audit_event.py` | F6 |
| `app/services/execution_logger.py` | F5 |
| `app/services/audit_service.py` | F6 |
| `app/services/recommended_actions.py` | F13 |
| `app/temporal/activities/preflight.py` | F2 |
| `app/controllers/api/v1/executions/logs_controller.py` | F5, F12 |
| `app/controllers/api/v1/executions/audit_controller.py` | F6, F12 |
| `app/controllers/api/v1/executions/steps_controller.py` | F7, F12 |
| `app/controllers/api/v1/executions/control_controller.py` | F10, F12 |
| `app/controllers/api/v1/executions/preflight_controller.py` | F2, F12 |

---

## Arquivos a Modificar

| Arquivo | Features |
|---------|----------|
| `app/models/execution.py` | F1, F14 |
| `app/models/execution_step.py` | F7 |
| `app/services/sse_publisher.py` | F3, F4 |
| `app/routes/sse.py` | F3, F4 |
| `app/temporal/workflows/docg_workflow.py` | F2, F9, F10 |
| `app/temporal/activities/base.py` | F1, F3, F5, F6 |
| `app/temporal/activities/signature.py` | F11 |
| `app/apps/clicksign/webhooks/signature_callback.py` | F11 |
| `app/apps/zapsign/webhooks/signature_callback.py` | F11 |
| `app/serializers/execution_serializer.py` | F1, F12 |

---

## Extensibilidade para Novos Apps

Todas as features são agnósticas de app. Qualquer novo app (futuro) automaticamente:

1. **Preflight**: Valida seus campos required, conexões
2. **Logs**: Registra execução com ExecutionLogger
3. **Audit**: Ações registradas automaticamente
4. **SSE**: Eventos emitidos pelo framework
5. **Recommended Actions**: Basta mapear códigos de erro

### Como Adicionar Novo App

```python
# app/apps/novo_app/__init__.py

class NovoApp(BaseApp):
    name = "Novo App"
    key = "novo-app"
    auth_type = AuthType.OAUTH2  # ou API_KEY

    def _setup(self):
        # Registrar actions
        self.register_action(MinhaAction())

        # Opcional: hooks, dynamic fields
        self.add_before_request_hook(self._add_auth)
```

---

**Última atualização:** 23 de Dezembro de 2025
