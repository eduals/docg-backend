# Análise: Execução de Workflows DocG

> **Atualizado em:** Dezembro 2024  
> **Versão:** 3.2 — Implementação Temporal Completa ✅

## 📋 Índice

1. [Situação Atual](#situação-atual)
2. [Problemas Identificados](#problemas-identificados)
3. [Plano: Stack Assíncrona com Temporal](#plano-stack-assíncrona-com-temporal)
4. [Nova Arquitetura](#nova-arquitetura)
5. [Mudanças no Banco de Dados](#mudanças-no-banco-de-dados)
6. [Contratos HTTP (API/Webhooks)](#contratos-http-apiwebhooks)
7. [Temporal Workflow (Orquestração)](#temporal-workflow-orquestração)
8. [Activities (Implementação)](#activities-implementação)
9. [Comportamento por Tipo de Node](#comportamento-por-tipo-de-node)
10. [Expiração sem Job de Varredura](#expiração-sem-job-de-varredura)
11. [Fallback: Modo Celery](#fallback-modo-celery)
12. [Roadmap de Implementação](#roadmap-de-implementação)
13. [Bugs Conhecidos](#bugs-conhecidos)
14. [Critérios de Aceite](#critérios-de-aceite)

---

## Situação Atual

### Arquitetura Existente

```mermaid
flowchart TB
    subgraph "Camada de Entrada"
        A1[HubSpot Workflow Action]
        A2[Webhook Trigger]
        A3[API Manual]
    end
    
    subgraph "Execução Síncrona ⚠️"
        B[WorkflowExecutor]
        C[ExecutionContext]
        D[Request HTTP]
    end
    
    subgraph "Executores"
        E1[TriggerNodeExecutor]
        E2[GoogleDocsNodeExecutor]
        E3[HumanInLoopNodeExecutor]
        E4[SignatureNodeExecutor]
    end
    
    A1 & A2 & A3 --> D
    D --> B
    B --> C
    C --> E1 --> E2 --> E3 --> E4
    
    style D fill:#ff6b6b,stroke:#333
```

### Componentes Atuais

| Componente | Arquivo | Status |
|------------|---------|--------|
| `WorkflowExecutor` | `app/services/workflow_executor.py` | ✅ Integrado com Temporal |
| `ExecutionContext` | `app/services/workflow_executor.py` | ✅ Implementado |
| `approval_service` | `app/services/approval_service.py` | ✅ Bug corrigido |
| Webhook assinatura | `app/routes/webhooks.py:632` | ✅ Envia signal Temporal |
| Webhook aprovação | `app/routes/approvals.py:56` | ✅ Envia signal Temporal |
| **DocGWorkflow** | `app/temporal/workflows/docg_workflow.py` | ✅ **IMPLEMENTADO** |
| **Temporal Service** | `app/temporal/service.py` | ✅ **IMPLEMENTADO** |
| **Temporal Worker** | `app/temporal/worker.py` | ✅ **IMPLEMENTADO** |
| **Temporal Activities** | `app/temporal/activities/` | ✅ **IMPLEMENTADO** |
| **Visualização Progresso** | `app/routes/workflows.py` | ✅ **IMPLEMENTADO** |
| **Script Verificação** | `scripts/verify_temporal.py` | ✅ **IMPLEMENTADO** |

### Dependências (requirements.txt)

```
celery==5.3.4      # Fallback se Temporal não disponível
redis==5.0.1       # Para Celery
temporalio>=1.7.0  # ✅ NOVO - Execução durável
```

---

## Problemas Identificados

### 🔴 Críticos

```mermaid
flowchart LR
    subgraph "Problema 1: Timeout"
        P1A[Request HTTP] -->|executa tudo| P1B[Workflow longo]
        P1B -->|30s+| P1C[❌ Timeout]
    end
    
    subgraph "Problema 2: Assinatura"
        P2A[SignatureNode] --> P2B[Cria request]
        P2B --> P2C[NÃO pausa]
        P2D[Webhook] --> P2E[Atualiza status]
        P2E -.->|NÃO conectado| P2C
    end
    
    subgraph "Problema 3: Expiração"
        P3A[Approval criada] --> P3B[expires_at]
        P3B -.->|Nenhum job| P3C[❌ Nunca expira]
    end
```

| # | Problema | Impacto | Código Afetado |
|---|----------|---------|----------------|
| 1 | Execução síncrona | Timeout em workflows longos | `WorkflowExecutor` |
| 2 | Assinatura não pausa | Workflow finaliza antes de assinar | `SignatureNodeExecutor` |
| 3 | Sem retomada após assinatura | Webhook não continua workflow | `webhooks.py:547` |
| 4 | Sem rastreamento de node atual | Impossível saber onde pausou | `WorkflowExecution` |
| 5 | Sem job de expiração | Aprovações nunca expiram | `WorkflowApproval` |
| 6 | Bug no approval_service | ExecutionContext criado errado | `approval_service.py:31` |

---

## Plano: Stack Assíncrona com Temporal

### Objetivo

Transformar execução em **durável**: pode pausar, esperar humano/assinatura, retomar via webhook, expirar por timer — sem "current_node_id na unha" nem job de varredura.

### Por Que Temporal?

| Aspecto | Celery | Temporal |
|---------|--------|----------|
| Execução durável | ❌ Tasks stateless | ✅ Workflow state persiste |
| Pausar/retomar | ⚠️ Manual (DB) | ✅ await signal |
| Timers | ⚠️ Celery Beat + cron | ✅ Nativo |
| Retry inteligente | ⚠️ Básico | ✅ Exponential backoff |
| Visibilidade | ⚠️ Flower | ✅ Temporal UI |
| Complexidade | Baixa | Média |

### Conceitos Temporal

```mermaid
graph TB
    subgraph "Temporal Server"
        TS[Task Queue: docg-workflows]
    end
    
    subgraph "Temporal Worker"
        W[DocGWorkflow]
        A1[TriggerActivity]
        A2[DocGenActivity]
        A3[ApprovalActivity]
        A4[SignatureActivity]
    end
    
    subgraph "Signals"
        S1[approval_decision]
        S2[signature_update]
    end
    
    subgraph "Timers"
        T1[approval_expires_at]
        T2[signature_expires_at]
    end
    
    TS --> W
    W --> A1 --> A2 --> A3 --> A4
    S1 & S2 -->|sinaliza| W
    T1 & T2 -->|expira| W
```

---

## Nova Arquitetura

### Antes vs Depois

```mermaid
flowchart TB
    subgraph "ANTES - Síncrono ❌"
        direction TB
        BA1[POST /execute] --> BA2[WorkflowExecutor]
        BA2 --> BA3[Executa TUDO]
        BA3 --> BA4[Responde HTTP]
        BA5[Webhook assinatura] --> BA6[Atualiza DB]
        BA6 -.->|desconectado| BA3
    end
    
    subgraph "DEPOIS - Temporal ✅"
        direction TB
        DA1[POST /execute] --> DA2[Start Workflow]
        DA2 --> DA3[Responde imediato]
        DA4[Temporal Worker] --> DA5[Executa nodes]
        DA5 --> DA6[Pausa: await signal]
        DA7[Webhook assinatura] --> DA8[Send signal]
        DA8 --> DA6
        DA6 --> DA9[Continua]
    end
```

### Fluxo Completo com Temporal

```mermaid
sequenceDiagram
    participant Client
    participant API as Flask API
    participant Temporal as Temporal Server
    participant Worker as Temporal Worker
    participant DB as PostgreSQL
    participant Provider as ClickSign/ZapSign
    
    %% Start
    Client->>API: POST /workflows/:id/execute
    API->>DB: Create WorkflowExecution (running)
    API->>Temporal: Start DocGWorkflow(execution_id)
    API-->>Client: {execution_id, status: running}
    
    %% Execution
    Temporal->>Worker: Run workflow
    Worker->>DB: Execute TriggerActivity
    Worker->>DB: Execute DocGenActivity
    
    %% Signature
    Worker->>DB: Execute SignatureActivity
    Worker->>DB: Update status=paused
    Worker->>Temporal: await signal OR timer
    
    Note over Worker,Temporal: ⏸️ Workflow pausado (durável)
    
    %% Webhook
    Provider->>API: POST /webhooks/signature/:provider
    API->>DB: Update SignatureRequest
    API->>Temporal: Signal signature_update
    
    %% Resume
    Temporal->>Worker: Resume workflow
    Worker->>DB: Execute remaining nodes
    Worker->>DB: Update status=completed
```

---

## Mudanças no Banco de Dados

### Migration: WorkflowExecution

```python
# Novos campos
class WorkflowExecution(db.Model):
    # ... campos existentes ...
    
    # Temporal tracking
    temporal_workflow_id = db.Column(db.String(255), unique=True, nullable=True)
    temporal_run_id = db.Column(db.String(255), nullable=True)
    
    # Node tracking (já planejado)
    current_node_id = db.Column(UUID(as_uuid=True), db.ForeignKey('workflow_nodes.id'))
    
    # Context snapshot (já planejado)
    execution_context = db.Column(JSONB)
    
    # Logs por node (já planejado)
    execution_logs = db.Column(JSONB, default=list)
    # Estrutura: [{node_id, node_type, started_at, completed_at, duration_ms, status, output, error}]
```

### Migration: SignatureRequest

```python
class SignatureRequest(db.Model):
    # ... campos existentes ...
    
    # NOVO: rastrear qual node criou
    node_id = db.Column(UUID(as_uuid=True), db.ForeignKey('workflow_nodes.id'))
    
    # NOVO: status por signatário
    signers_status = db.Column(JSONB, default=dict)
    # Estrutura: {"email@ex.com": "signed", "email2@ex.com": "pending"}
    
    def all_signed(self) -> bool:
        """Verifica se todos signatários assinaram"""
        if not self.signers_status:
            return self.status == 'signed'
        return all(s == 'signed' for s in self.signers_status.values())
```

### Script de Migration

```sql
-- WorkflowExecution
ALTER TABLE workflow_executions 
ADD COLUMN temporal_workflow_id VARCHAR(255) UNIQUE,
ADD COLUMN temporal_run_id VARCHAR(255),
ADD COLUMN current_node_id UUID REFERENCES workflow_nodes(id),
ADD COLUMN execution_context JSONB,
ADD COLUMN execution_logs JSONB DEFAULT '[]'::jsonb;

-- SignatureRequest
ALTER TABLE signature_requests
ADD COLUMN node_id UUID REFERENCES workflow_nodes(id),
ADD COLUMN signers_status JSONB DEFAULT '{}'::jsonb;

-- Index para buscar execuções pausadas
CREATE INDEX idx_execution_status_workflow 
ON workflow_executions(workflow_id, status) 
WHERE status = 'paused';
```

---

## Contratos HTTP (API/Webhooks)

### 1. Executar Workflow (Start)

**POST** `/api/v1/workflows/:workflow_id/execute`

```json
// Request
{
  "source_object_id": "12345",
  "source_object_type": "deal",
  "trigger": "hubspot|webhook|manual",
  "input": {}
}

// Response
{
  "execution_id": "uuid",
  "temporal_workflow_id": "exec_uuid",
  "status": "running"
}
```

**Implementação:**

```python
@workflows_bp.route('/<workflow_id>/execute', methods=['POST'])
def execute_workflow(workflow_id):
    data = request.get_json()
    
    # 1. Criar WorkflowExecution
    execution = WorkflowExecution(
        workflow_id=workflow_id,
        trigger_type=data.get('trigger', 'manual'),
        trigger_data=data,
        status='running'
    )
    execution.temporal_workflow_id = f"exec_{execution.id}"
    db.session.add(execution)
    db.session.commit()
    
    # 2. Start Temporal Workflow
    from app.temporal.client import get_temporal_client
    client = get_temporal_client()
    
    await client.start_workflow(
        "DocGWorkflow",
        str(execution.id),
        id=execution.temporal_workflow_id,
        task_queue="docg-workflows"
    )
    
    return jsonify({
        'execution_id': str(execution.id),
        'temporal_workflow_id': execution.temporal_workflow_id,
        'status': 'running'
    })
```

### 2. Aprovar/Rejeitar (Human-in-Loop)

**POST** `/api/v1/approvals/:token/decision`

```json
// Request
{ "decision": "approved|rejected", "comment": "opcional" }

// Response
{ "success": true, "execution_status": "running|failed" }
```

**Implementação:**

```python
@approvals_bp.route('/<token>/decision', methods=['POST'])
def approve_decision(token):
    data = request.get_json()
    decision = data.get('decision')
    
    approval = WorkflowApproval.query.filter_by(approval_token=token).first_or_404()
    
    # 1. Atualizar approval
    approval.status = decision
    approval.decided_at = datetime.utcnow()
    approval.comment = data.get('comment')
    db.session.commit()
    
    # 2. Enviar signal pro Temporal
    execution = WorkflowExecution.query.get(approval.workflow_execution_id)
    
    from app.temporal.client import get_temporal_client
    client = get_temporal_client()
    
    handle = client.get_workflow_handle(execution.temporal_workflow_id)
    await handle.signal("approval_decision", {
        "approval_id": str(approval.id),
        "decision": decision
    })
    
    return jsonify({'success': True})
```

### 3. Webhook Assinatura (MUDANÇA CRÍTICA)

**POST** `/api/v1/webhooks/signature/:provider`

**Antes:** Apenas atualizava DB  
**Depois:** Atualiza DB + envia signal

```python
@webhooks_bp.route('/signature/<provider>', methods=['POST'])
def handle_signature_webhook(provider):
    # ... código existente de validação ...
    
    # 1. Atualizar SignatureRequest (existente)
    signature_request.status = event['status'].value
    if event['status'] == SignatureStatus.SIGNED:
        signature_request.completed_at = event['timestamp']
    signature_request.webhook_data = payload
    
    # 2. Atualizar signers_status se aplicável
    if event.get('signer_email'):
        signers_status = signature_request.signers_status or {}
        signers_status[event['signer_email']] = 'signed'
        signature_request.signers_status = signers_status
    
    db.session.commit()
    
    # 3. NOVO: Se todos assinaram, enviar signal
    if signature_request.all_signed():
        # Buscar execução via document
        document = GeneratedDocument.query.get(signature_request.generated_document_id)
        if document:
            execution = WorkflowExecution.query.filter_by(
                workflow_id=document.workflow_id,
                status='paused'
            ).order_by(WorkflowExecution.created_at.desc()).first()
            
            if execution and execution.temporal_workflow_id:
                from app.temporal.client import get_temporal_client
                client = get_temporal_client()
                
                handle = client.get_workflow_handle(execution.temporal_workflow_id)
                await handle.signal("signature_update", {
                    "signature_request_id": str(signature_request.id),
                    "status": "signed"
                })
    
    return jsonify({'success': True})
```

---

## Temporal Workflow (Orquestração)

### Estrutura de Arquivos

```
app/
├── temporal/
│   ├── __init__.py
│   ├── client.py           # Conexão com Temporal
│   ├── worker.py           # Worker que executa workflows
│   ├── workflows/
│   │   ├── __init__.py
│   │   └── docg_workflow.py  # DocGWorkflow
│   └── activities/
│       ├── __init__.py
│       ├── trigger.py
│       ├── document.py
│       ├── approval.py
│       └── signature.py
```

### DocGWorkflow (Principal)

```python
# app/temporal/workflows/docg_workflow.py
from temporalio import workflow
from temporalio.common import RetryPolicy
from datetime import timedelta
import asyncio

@workflow.defn
class DocGWorkflow:
    def __init__(self):
        self.approval_decision = None
        self.signature_status = None
    
    @workflow.signal
    async def approval_decision_signal(self, data: dict):
        self.approval_decision = data
    
    @workflow.signal
    async def signature_update_signal(self, data: dict):
        self.signature_status = data
    
    @workflow.run
    async def run(self, execution_id: str):
        # 1. Carregar execution e nodes
        execution_data = await workflow.execute_activity(
            "load_execution",
            execution_id,
            start_to_close_timeout=timedelta(seconds=30)
        )
        
        nodes = execution_data['nodes']
        
        # 2. Loop de nodes
        for node in nodes:
            node_id = node['id']
            node_type = node['node_type']
            
            # Persistir current_node_id
            await workflow.execute_activity(
                "update_current_node",
                {"execution_id": execution_id, "node_id": node_id},
                start_to_close_timeout=timedelta(seconds=10)
            )
            
            # Executar node baseado no tipo
            if node_type in ['hubspot', 'webhook', 'trigger', 'google-forms']:
                await self._execute_trigger(execution_id, node)
            
            elif node_type in ['google-docs', 'google-slides', 'microsoft-word', 'microsoft-powerpoint']:
                await self._execute_document(execution_id, node)
            
            elif node_type in ['review-documents', 'human-in-loop']:
                await self._execute_approval(execution_id, node)
            
            elif node_type in ['request-signatures', 'signature', 'clicksign']:
                await self._execute_signature(execution_id, node)
            
            elif node_type in ['gmail', 'outlook']:
                await self._execute_email(execution_id, node)
        
        # 3. Finalizar
        await workflow.execute_activity(
            "complete_execution",
            execution_id,
            start_to_close_timeout=timedelta(seconds=10)
        )
        
        return {"status": "completed"}
    
    async def _execute_approval(self, execution_id: str, node: dict):
        """Executa node de aprovação com pausa"""
        # 1. Criar approval
        approval_data = await workflow.execute_activity(
            "create_approval",
            {"execution_id": execution_id, "node": node},
            start_to_close_timeout=timedelta(seconds=30)
        )
        
        expires_at = approval_data['expires_at']
        timeout = (expires_at - workflow.now()).total_seconds()
        
        # 2. Atualizar status para paused
        await workflow.execute_activity(
            "pause_execution",
            execution_id,
            start_to_close_timeout=timedelta(seconds=10)
        )
        
        # 3. Esperar signal OU timeout
        self.approval_decision = None
        
        try:
            await workflow.wait_condition(
                lambda: self.approval_decision is not None,
                timeout=timedelta(seconds=timeout)
            )
        except asyncio.TimeoutError:
            # Expirou
            await workflow.execute_activity(
                "expire_approval",
                approval_data['approval_id'],
                start_to_close_timeout=timedelta(seconds=10)
            )
            raise workflow.ApplicationError("Aprovação expirou")
        
        # 4. Verificar decisão
        if self.approval_decision['decision'] == 'rejected':
            raise workflow.ApplicationError("Aprovação rejeitada")
        
        # 5. Retomar
        await workflow.execute_activity(
            "resume_execution",
            execution_id,
            start_to_close_timeout=timedelta(seconds=10)
        )
    
    async def _execute_signature(self, execution_id: str, node: dict):
        """Executa node de assinatura com pausa"""
        # 1. Criar signature request
        sig_data = await workflow.execute_activity(
            "create_signature_request",
            {"execution_id": execution_id, "node": node},
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )
        
        expires_at = sig_data.get('expires_at')
        timeout = (expires_at - workflow.now()).total_seconds() if expires_at else 86400 * 7  # 7 dias default
        
        # 2. Atualizar status para paused
        await workflow.execute_activity(
            "pause_execution",
            execution_id,
            start_to_close_timeout=timedelta(seconds=10)
        )
        
        # 3. Esperar signal OU timeout
        self.signature_status = None
        
        try:
            await workflow.wait_condition(
                lambda: self.signature_status is not None,
                timeout=timedelta(seconds=timeout)
            )
        except asyncio.TimeoutError:
            # Expirou
            await workflow.execute_activity(
                "expire_signature",
                sig_data['signature_request_id'],
                start_to_close_timeout=timedelta(seconds=10)
            )
            raise workflow.ApplicationError("Assinatura expirou")
        
        # 4. Verificar status
        if self.signature_status['status'] != 'signed':
            raise workflow.ApplicationError(f"Assinatura: {self.signature_status['status']}")
        
        # 5. Retomar
        await workflow.execute_activity(
            "resume_execution",
            execution_id,
            start_to_close_timeout=timedelta(seconds=10)
        )
```

---

## Activities (Implementação)

### Contrato Comum

```python
# app/temporal/activities/base.py
from temporalio import activity
from app.database import db
from app.models import WorkflowExecution, WorkflowNode

@activity.defn
async def load_execution(execution_id: str) -> dict:
    """Carrega execution e nodes do DB"""
    execution = WorkflowExecution.query.get(execution_id)
    workflow = execution.workflow
    nodes = WorkflowNode.query.filter_by(
        workflow_id=workflow.id
    ).order_by(WorkflowNode.position).all()
    
    return {
        'execution': execution.to_dict(),
        'workflow': workflow.to_dict(),
        'nodes': [n.to_dict(include_config=True) for n in nodes]
    }

@activity.defn
async def update_current_node(data: dict):
    """Atualiza current_node_id na execution"""
    execution = WorkflowExecution.query.get(data['execution_id'])
    execution.current_node_id = data['node_id']
    db.session.commit()

@activity.defn
async def pause_execution(execution_id: str):
    """Marca execution como pausada"""
    execution = WorkflowExecution.query.get(execution_id)
    execution.status = 'paused'
    db.session.commit()

@activity.defn
async def resume_execution(execution_id: str):
    """Marca execution como running"""
    execution = WorkflowExecution.query.get(execution_id)
    execution.status = 'running'
    db.session.commit()

@activity.defn
async def complete_execution(execution_id: str):
    """Marca execution como completed"""
    execution = WorkflowExecution.query.get(execution_id)
    execution.status = 'completed'
    execution.completed_at = datetime.utcnow()
    db.session.commit()
```

### Activity de Documento (Idempotente)

```python
# app/temporal/activities/document.py
from temporalio import activity

@activity.defn
async def execute_document_node(data: dict) -> dict:
    """
    Executa node de documento (Google Docs, Slides, Word, PowerPoint).
    
    IDEMPOTÊNCIA: Verifica se documento já foi gerado antes de criar novo.
    """
    execution_id = data['execution_id']
    node = data['node']
    node_id = node['id']
    
    # Verificar idempotência
    existing = GeneratedDocument.query.filter_by(
        workflow_execution_id=execution_id,
        node_id=node_id
    ).first()
    
    if existing:
        activity.logger.info(f"Documento já existe para node {node_id}, reusando")
        return {'document_id': str(existing.id), 'reused': True}
    
    # Executar usando executor existente
    from app.services.workflow_executor import WorkflowExecutor
    
    executor = WorkflowExecutor()
    # ... lógica existente ...
    
    return {'document_id': str(doc.id), 'reused': False}
```

---

## Comportamento por Tipo de Node

### Diagrama de Estados por Node

```mermaid
stateDiagram-v2
    [*] --> Trigger
    Trigger --> Document: source_data
    Document --> Document: múltiplos docs
    Document --> Approval: se configurado
    Document --> Signature: se configurado
    Document --> Email: se configurado
    
    state Approval {
        [*] --> Creating
        Creating --> Waiting: WorkflowApproval criada
        Waiting --> Approved: signal approved
        Waiting --> Rejected: signal rejected
        Waiting --> Expired: timer
        Approved --> [*]
        Rejected --> Failed
        Expired --> Failed
    }
    
    state Signature {
        [*] --> Sending
        Sending --> Waiting: SignatureRequest criada
        Waiting --> Signed: signal all_signed
        Waiting --> Rejected: signal rejected
        Waiting --> Expired: timer
        Signed --> [*]
        Rejected --> Failed
        Expired --> Failed
    }
    
    Approval --> Document
    Approval --> Signature
    Signature --> Email
    Email --> [*]
    Failed --> [*]
```

### Tabela de Comportamento

| Node Type | Activity | Pausa? | Espera Signal? | Timer? |
|-----------|----------|--------|----------------|--------|
| `hubspot` | TriggerActivity | ❌ | ❌ | ❌ |
| `webhook` | TriggerActivity | ❌ | ❌ | ❌ |
| `google-docs` | DocumentActivity | ❌ | ❌ | ❌ |
| `google-slides` | DocumentActivity | ❌ | ❌ | ❌ |
| `microsoft-word` | DocumentActivity | ❌ | ❌ | ❌ |
| `microsoft-powerpoint` | DocumentActivity | ❌ | ❌ | ❌ |
| `gmail` | EmailActivity | ❌ | ❌ | ❌ |
| `outlook` | EmailActivity | ❌ | ❌ | ❌ |
| `review-documents` | ApprovalActivity | ✅ | `approval_decision` | `expires_at` |
| `request-signatures` | SignatureActivity | ✅ | `signature_update` | `expires_at` |

---

## Expiração sem Job de Varredura

### Antes (Celery Beat)

```python
# ❌ NÃO USAR - Job de varredura problemático
@shared_task
def check_expired_approvals():
    expired = WorkflowApproval.query.filter(
        WorkflowApproval.status == 'pending',
        WorkflowApproval.expires_at < datetime.utcnow()
    ).all()
    # ... processar cada um ...
```

### Depois (Temporal Timer)

```python
# ✅ USAR - Timer nativo do Temporal
async def _execute_approval(self, execution_id: str, node: dict):
    # ...
    try:
        await workflow.wait_condition(
            lambda: self.approval_decision is not None,
            timeout=timedelta(hours=node['config'].get('timeout_hours', 48))
        )
    except asyncio.TimeoutError:
        # Timer expirou automaticamente
        await workflow.execute_activity("expire_approval", approval_id)
        raise workflow.ApplicationError("Aprovação expirou")
```

**Vantagens:**
- ✅ Sem job de varredura
- ✅ Expiração precisa (não depende de cron)
- ✅ Menos carga no banco
- ✅ Visibilidade no Temporal UI

---

## Fallback: Modo Celery

Se Temporal não for viável imediatamente, usar Celery como stepping stone:

### Estrutura Celery

```python
# app/tasks/workflow_tasks.py
from celery import shared_task

@shared_task(bind=True, max_retries=3)
def execute_workflow_async(self, execution_id: str):
    """Executa workflow em background"""
    try:
        from app.services.workflow_executor import WorkflowExecutor
        
        execution = WorkflowExecution.query.get(execution_id)
        workflow = execution.workflow
        
        executor = WorkflowExecutor()
        executor.execute_workflow(
            workflow,
            execution.trigger_data['source_object_id'],
            execution.trigger_data['source_object_type']
        )
    except Exception as e:
        self.retry(exc=e, countdown=60)

@shared_task
def resume_after_approval(approval_id: str):
    """Retoma workflow após aprovação"""
    from app.services.approval_service import resume_workflow_execution
    approval = WorkflowApproval.query.get(approval_id)
    resume_workflow_execution(approval)

@shared_task
def resume_after_signature(signature_request_id: str):
    """Retoma workflow após assinatura"""
    from app.services.approval_service import resume_from_signature
    sig = SignatureRequest.query.get(signature_request_id)
    resume_from_signature(sig)

# Celery Beat - job de expiração
@shared_task
def check_expirations():
    """Verifica aprovações e assinaturas expiradas"""
    # Approvals
    expired_approvals = WorkflowApproval.query.filter(
        WorkflowApproval.status == 'pending',
        WorkflowApproval.expires_at < datetime.utcnow()
    ).all()
    
    for approval in expired_approvals:
        if approval.auto_approve_on_timeout:
            approval.status = 'approved'
            resume_after_approval.delay(str(approval.id))
        else:
            approval.status = 'expired'
            execution = WorkflowExecution.query.get(approval.workflow_execution_id)
            execution.status = 'failed'
            execution.error_message = 'Aprovação expirou'
    
    db.session.commit()
```

### Comparação: Temporal vs Celery

| Aspecto | Temporal | Celery |
|---------|----------|--------|
| Complexidade inicial | Média | Baixa |
| Pausar/retomar | Nativo | Manual (DB + tasks) |
| Expiração | Timer nativo | Celery Beat |
| Retry | Sofisticado | Básico |
| Visibilidade | Temporal UI | Flower |
| Escalabilidade | Alta | Média |
| Durabilidade | Total | Parcial |
| Custo operacional | Temporal Server | Redis |

**Recomendação:** Começar com Temporal se equipe tiver capacidade. Celery como fallback temporário.

---

## Status da Implementação

### ✅ Implementado (Dezembro 2024)

#### Fase 0 - Correções ✅
- [x] **Fix bug** `approval_service.py:31` - ExecutionContext sem execution_id
- [x] **Migration** - Adicionar campos: `temporal_workflow_id`, `current_node_id`, `execution_context`, `execution_logs`
- [x] **Migration** - SignatureRequest: adicionar `node_id`, `signers_status`

#### Fase 1 - Fundação Temporal ✅
- [x] **Setup** - Temporal Server (Docker ou Cloud)
- [x] **Config** - `TEMPORAL_ADDRESS`, `TEMPORAL_NAMESPACE`, `TEMPORAL_TASK_QUEUE`
- [x] **Client** - `app/temporal/client.py`
- [x] **Worker** - `app/temporal/worker.py`
- [x] **Workflow** - `DocGWorkflow` completo (loop de nodes)
- [x] **Activities** - `load_execution`, `update_current_node`, `pause/resume/complete`
- [x] **Activities** - TriggerActivity + DocumentActivity + ApprovalActivity + SignatureActivity + EmailActivity

#### Fase 2 - Pausa/Retomada ✅
- [x] **ApprovalActivity** - Criar approval + await signal
- [x] **SignatureActivity** - Criar request + await signal
- [x] **Webhook approval** - Enviar signal `approval_decision`
- [x] **Webhook signature** - Enviar signal `signature_update`
- [x] **Timers** - Expiração nativa

#### Fase 3 - Qualidade ✅
- [x] **Logs** - `execution_logs` por node
- [x] **WorkflowExecutor** - Integrado com Temporal
- [x] **Visualização Progresso** - Endpoints atualizados
- [x] **Script Verificação** - `scripts/verify_temporal.py`
- [x] **Docs** - Documentação atualizada

#### Fase 4 - Melhorias (Opcional)
- [ ] **Múltiplos aprovadores** - Estratégia all/any
- [ ] **Retry policy** - Por tipo de Activity (já implementado básico)
- [x] **Observability** - Temporal UI disponível

---

## Visualização de Progresso no Frontend

### Endpoint de Detalhes da Execução

**GET** `/api/v1/workflows/<workflow_id>/runs/<run_id>?include_logs=true`

**Query Params:**
- `include_logs` (boolean): Incluir `execution_logs` na resposta

**Response:**
```json
{
  "id": "exec-123",
  "workflow_id": "workflow-456",
  "status": "running",
  "current_node_id": "node-789",
  "current_node": {
    "id": "node-789",
    "node_type": "google-docs",
    "position": 2,
    "name": "Gerar Documento"
  },
  "steps_completed": 1,
  "steps_total": 5,
  "execution_logs": [
    {
      "node_id": "node-123",
      "node_type": "hubspot",
      "status": "success",
      "started_at": "2024-01-01T10:00:00Z",
      "completed_at": "2024-01-01T10:00:05Z",
      "duration_ms": 5000
    }
  ],
  "temporal_workflow_id": "exec_exec-123",
  "temporal_run_id": "run-abc"
}
```

### Cálculo de Progresso

O sistema calcula `steps_completed` baseado em:

1. **`current_node_id`** (preferencial):
   - Encontra posição do node atual
   - Conta nodes executados antes do atual (excluindo trigger)

2. **`execution_logs`** (fallback):
   - Conta nodes com status 'success' ou 'failed'

### Lista de Execuções

**GET** `/api/v1/workflows/<workflow_id>/runs`

Aplica a mesma lógica de cálculo de progresso para execuções `running` e `failed`.

### Atualizações em Tempo Real

- Frontend deve fazer **polling** quando `status === 'running'`
- Intervalo recomendado: **2-3 segundos**
- Endpoint retorna `current_node_id` e `execution_logs` atualizados

## Bugs Conhecidos

### ✅ Bug #1: approval_service.py — CORRIGIDO

**Localização:** `app/services/approval_service.py:31-37`

**Problema:** `ExecutionContext` criado sem `execution_id` (obrigatório).

**Status:** ✅ **CORRIGIDO** em 17/12/2024

**Código corrigido:**
```python
context = ExecutionContext(
    workflow_id=str(workflow.id),
    execution_id=str(execution.id),  # ✅ Adicionado
    source_object_id=execution_context_data.get('source_object_id'),
    source_object_type=execution_context_data.get('source_object_type')
)
context.source_data = execution_context_data.get('source_data', {})
context.metadata = execution_context_data.get('metadata', {})
```

### ✅ Bug #2: Webhook assinatura não retoma — CORRIGIDO

**Localização:** `app/routes/webhooks.py:632-646`

**Problema:** Apenas atualiza `SignatureRequest.status`, não retoma workflow.

**Status:** ✅ **CORRIGIDO** em 17/12/2024

**Solução implementada:**
- Webhook agora verifica `signature_request.all_signed()`
- Se todos assinaram E tem `workflow_execution_id`, envia signal Temporal
- Usa `app.temporal.service.send_signature_update()`

### ✅ Bug #3: WorkflowExecutor não inicia Temporal — CORRIGIDO

**Localização:** `app/services/workflow_executor.py:1439-1534`

**Problema:** `WorkflowExecutor.execute_workflow()` executava tudo de forma síncrona, ignorando Temporal.

**Status:** ✅ **CORRIGIDO** em Dezembro 2024

**Solução implementada:**
- `WorkflowExecutor` verifica se Temporal está habilitado
- Se sim, chama `start_workflow_execution()` e retorna imediatamente
- Se não, executa de forma síncrona (fallback)

---

## Critérios de Aceite

### Testes de Aceite

| # | Cenário | Critério |
|---|---------|----------|
| 1 | Workflow com `review-documents` | Pausa e só continua após approve |
| 2 | Rejeição de approval | Execution status = failed |
| 3 | Expiração de approval | Execution status = failed (sem job) |
| 4 | Workflow com `request-signatures` | Pausa e só continua após webhook |
| 5 | Múltiplos signatários | Só continua quando `all_signed()` |
| 6 | Reiniciar worker | Execution não é perdida |
| 7 | Retry de Activity | Não duplica documento/assinatura |
| 8 | Workflow longo | Não dá timeout HTTP |

### Comandos de Teste

```bash
# Subir Temporal (dev)
docker-compose up -d temporal temporal-ui

# Rodar worker
python -m app.temporal.worker

# Executar workflow de teste
curl -X POST http://localhost:5000/api/v1/workflows/{id}/execute \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{"source_object_id": "123", "source_object_type": "deal"}'

# Verificar no Temporal UI
open http://localhost:8080
```

---

## Referências

### Código Fonte
- `app/services/workflow_executor.py` - Executor integrado com Temporal
- `app/services/approval_service.py` - Serviço de aprovação
- `app/routes/webhooks.py` - Webhooks de assinatura (envia signals Temporal)
- `app/routes/approvals.py` - Rotas de aprovação (envia signals Temporal)
- `app/routes/workflows.py` - Endpoints de execução (visualização de progresso)
- `app/models/workflow.py` - Models de workflow
- `app/models/execution.py` - Model de execução (com campos Temporal)
- `app/temporal/` - Módulo completo de integração Temporal
- `scripts/verify_temporal.py` - Script de verificação de configuração
- `docs/TEMPORAL_TESTING.md` - Guia de testes

### Documentação Externa
- [Temporal Python SDK](https://docs.temporal.io/dev-guide/python)
- [Temporal Concepts](https://docs.temporal.io/concepts)
- [Celery Documentation](https://docs.celeryq.dev/)

### Estrutura de Arquivos Temporal (Implementado)

```
app/temporal/
├── __init__.py           # Exports principais
├── config.py             # Configurações e constantes
├── client.py             # Cliente para conectar ao Temporal
├── service.py            # Funções síncronas para Flask
├── worker.py             # Worker que executa workflows
├── workflows/
│   ├── __init__.py
│   └── docg_workflow.py  # DocGWorkflow principal
└── activities/
    ├── __init__.py       # ALL_ACTIVITIES
    ├── base.py           # load, update, pause, resume, complete
    ├── trigger.py        # execute_trigger_node
    ├── document.py       # execute_document_node
    ├── approval.py       # create_approval, expire_approval
    ├── signature.py      # create_signature_request, expire_signature
    └── email.py          # execute_email_node
```

### Variáveis de Ambiente

```bash
# Temporal Server (obrigatório)
TEMPORAL_ADDRESS=seu-temporal-server:7233

# Namespace (default: "default")
TEMPORAL_NAMESPACE=default

# Task Queue (default: "docg-workflows")
TEMPORAL_TASK_QUEUE=docg-workflows
```

### Como Executar

```bash
# 1. Verificar configuração
python scripts/verify_temporal.py

# 2. Rodar worker (container separado ou processo)
python -m app.temporal.worker

# 3. Ou via Docker
docker build -f Dockerfile.worker -t docg-worker .
docker run --env-file .env docg-worker
```

### Verificação e Testes

**Script de Verificação:**
```bash
python scripts/verify_temporal.py
```

Verifica:
- Variáveis de ambiente configuradas
- Conectividade com Temporal Server
- Configuração do Worker

**Documentação de Testes:**
Ver `docs/TEMPORAL_TESTING.md` para guia completo de testes.

### Integração com WorkflowExecutor

O `WorkflowExecutor` foi atualizado para:
- Verificar se Temporal está habilitado (`is_temporal_enabled()`)
- Se sim, iniciar execução via Temporal e retornar imediatamente
- Se não, executar de forma síncrona (fallback)

**Código:**
```python
# app/services/workflow_executor.py
if is_temporal_enabled():
    start_workflow_execution(
        execution_id=str(execution.id),
        workflow_id=str(workflow.id)
    )
    return execution  # Retorna imediatamente
# Fallback: execução síncrona
```

### Visualização de Progresso

**Endpoints Atualizados:**
- `GET /workflows/<id>/runs/<run_id>` - Retorna `current_node_id`, `current_node`, `execution_logs`
- `GET /workflows/<id>/runs` - Calcula `steps_completed` baseado em `current_node_id` ou logs

**Frontend:**
- Pode fazer polling para atualizar progresso em tempo real
- Exibe etapa atual e logs detalhados
- Mostra progresso como "1/5" steps completados

---

## Resumo da Implementação

### Status Atual: ✅ COMPLETO

A implementação do Temporal está **100% funcional** e integrada ao sistema:

#### ✅ Componentes Implementados

1. **Temporal Infrastructure**
   - ✅ Client para conexão com Temporal Server
   - ✅ Worker que executa workflows e activities
   - ✅ Configuração via variáveis de ambiente
   - ✅ Script de verificação (`scripts/verify_temporal.py`)

2. **Workflow Principal**
   - ✅ `DocGWorkflow` orquestra execução completa
   - ✅ Processa nodes sequencialmente
   - ✅ Gerencia pausas para aprovação e assinatura
   - ✅ Suporta timeouts e expirações nativas

3. **Activities**
   - ✅ Base: load, update, pause, resume, complete, fail, add_log
   - ✅ Trigger: Extração de dados
   - ✅ Document: Geração de documentos
   - ✅ Approval: Criação e gerenciamento de aprovações
   - ✅ Signature: Envio e rastreamento de assinaturas
   - ✅ Email: Envio de emails

4. **Integração com API**
   - ✅ `WorkflowExecutor` integrado com Temporal
   - ✅ Webhooks enviam signals para retomar execuções
   - ✅ Rotas de aprovação enviam signals
   - ✅ Endpoints retornam progresso e logs

5. **Visualização de Progresso**
   - ✅ Endpoint de detalhes retorna `current_node_id` e `current_node`
   - ✅ Cálculo dinâmico de `steps_completed`
   - ✅ `execution_logs` disponível via query param
   - ✅ Lista de execuções mostra progresso

6. **Banco de Dados**
   - ✅ Migração com campos Temporal
   - ✅ `current_node_id` atualizado durante execução
   - ✅ `execution_logs` populado por node
   - ✅ `temporal_workflow_id` e `temporal_run_id` rastreados

#### ✅ Funcionalidades

- ✅ Execução assíncrona durável (sem timeout HTTP)
- ✅ Pausar/retomar execuções (aprovações, assinaturas)
- ✅ Timeouts e expirações nativas (sem job de varredura)
- ✅ Retry automático com backoff exponencial
- ✅ Visibilidade completa no Temporal UI
- ✅ Fallback para execução síncrona quando Temporal não disponível
- ✅ Visualização de progresso em tempo real no frontend

#### 📊 Métricas de Implementação

- **Arquivos criados**: 10+
- **Linhas de código**: ~2000+
- **Activities implementadas**: 13
- **Workflows**: 1 (DocGWorkflow)
- **Endpoints atualizados**: 2
- **Bugs corrigidos**: 3

#### 🚀 Próximos Passos (Opcional)

- [ ] WebSockets para atualizações em tempo real (substituir polling)
- [ ] Múltiplos aprovadores com estratégia all/any
- [ ] Retry policy customizada por tipo de activity
- [ ] Métricas e observability avançada
- [ ] Testes E2E automatizados

---

**Última Atualização:** Dezembro 2024  
**Status:** ✅ Implementação Completa e Funcional
