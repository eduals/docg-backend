# Análise: Execução de Workflows

## Estrutura Atual

### Arquitetura de Execução

**WorkflowExecutor** (`app/services/workflow_executor.py`)
- Orquestra execução sequencial de nodes
- Cada node tem um executor específico (TriggerNodeExecutor, GoogleDocsNodeExecutor, etc.)
- Execução é síncrona e sequencial (um node após o outro)

**ExecutionContext**
- Mantém estado durante execução
- Armazena: `source_data`, `generated_documents`, `signature_requests`, `metadata`
- Passado entre nodes sequencialmente

**WorkflowExecution**
- Registro de cada execução
- Status: `running`, `completed`, `failed`, `paused`
- Armazena: `trigger_data`, `execution_time_ms`, `ai_metrics`

### Tipos de Nodes Suportados

1. **trigger** - Extrai dados da fonte (HubSpot/webhook)
2. **google-docs** - Gera documento Google Docs
3. **google-slides** - Gera apresentação Google Slides
4. **microsoft-word** - Gera documento Word
5. **microsoft-powerpoint** - Gera apresentação PowerPoint
6. **gmail** - Envia email via SMTP
7. **outlook** - Envia email via Microsoft Graph
8. **human-in-loop** - Pausa para aprovação
9. **signature** - Envia para assinatura (ClickSign, ZapSign)
10. **webhook** - Chama webhook externo

## Comportamento Atual

### Execução Sequencial

1. Workflow é executado via `WorkflowExecutor.execute_workflow()`
2. Nodes são processados em ordem (`position`)
3. Cada node recebe `ExecutionContext` e retorna atualizado
4. Erros em nodes críticos interrompem execução
5. Execução termina quando todos nodes são processados

### Espera para Aprovação (Human-in-Loop)

**Implementado:**
- Node `human-in-loop` pausa execução
- Cria `WorkflowApproval` com token único
- Salva snapshot do `ExecutionContext` em `execution_context`
- Marca `WorkflowExecution.status = 'paused'`
- Envia email com link de aprovação (preparado, não enviado ainda)

**Retomada:**
- `approval_service.resume_workflow_execution()` retoma execução
- Restaura `ExecutionContext` do snapshot
- Continua a partir do próximo node após o `human-in-loop`
- Implementado em `app/routes/approvals.py`

### Espera para Assinatura

**Implementado:**
- Node `signature` envia documento para assinatura
- Cria `SignatureRequest` com status `pending`
- Webhook recebe eventos de assinatura (`/api/v1/webhooks/signature/<provider>`)
- Atualiza `SignatureRequest.status` quando assinado

**FALTA:**
- **Não há retomada automática após assinatura**
- Workflow não continua após documento ser assinado
- Webhook apenas atualiza status, não retoma execução

## O Que Falta Implementar

### 1. Retomada Automática Após Assinatura

**Problema:** Quando documento é assinado, workflow não continua automaticamente.

**Solução necessária:**
- No webhook de assinatura (`app/routes/webhooks.py:545`), após atualizar `SignatureRequest.status = 'signed'`:
  1. Buscar `GeneratedDocument` via `SignatureRequest.generated_document_id`
  2. Buscar `WorkflowExecution` mais recente com `workflow_id = GeneratedDocument.workflow_id` e `status = 'paused'`
  3. Verificar se execução pausou no node de assinatura (comparar `current_node_id` ou buscar node que criou `SignatureRequest`)
  4. Chamar função similar a `resume_workflow_execution()` para continuar workflow
  5. Continuar a partir do próximo node após o node de assinatura

**Arquivos a modificar:**
- `app/routes/webhooks.py` - Adicionar lógica de retomada no webhook
- `app/services/approval_service.py` - Criar função genérica `resume_workflow_execution_from_node()` ou similar

**Nota:** Para identificar qual node de assinatura criou a `SignatureRequest`, pode-se:
- Adicionar campo `node_id` em `SignatureRequest` (recomendado)
- Ou buscar no `ExecutionContext.metadata` da execução pausada qual node criou a assinatura

### 2. Rastreamento de Node Atual na Execução

**Problema:** `WorkflowExecution` não armazena qual node está sendo executado ou onde pausou.

**Solução necessária:**
- Adicionar campo `current_node_id` em `WorkflowExecution` (ou usar `execution_context.metadata.current_node_position`)
- Quando workflow pausa (human-in-loop ou assinatura), salvar `node_id` onde pausou
- Na retomada, usar esse `node_id` para saber de onde continuar

**Arquivos a modificar:**
- `app/models/execution.py` - Adicionar `current_node_id` (opcional, pode usar metadata)
- `app/services/workflow_executor.py` - Salvar `current_node_id` ao pausar
- `app/services/approval_service.py` - Usar `current_node_id` na retomada

### 3. Múltiplas Aprovações Simultâneas

**Problema:** Se `human-in-loop` tem múltiplos aprovadores, workflow só retoma quando TODOS aprovarem? Ou quando o primeiro aprovar?

**Status atual:** Cria múltiplas `WorkflowApproval`, mas retoma quando qualquer uma é aprovada.

**Solução necessária:**
- Definir comportamento: "todos devem aprovar" vs "qualquer um pode aprovar"
- Adicionar campo `approval_strategy` no config do node (`all` ou `any`)
- Implementar lógica de verificação antes de retomar

**Arquivos a modificar:**
- `app/services/workflow_executor.py` - HumanInLoopNodeExecutor: salvar estratégia
- `app/services/approval_service.py` - Verificar se todos aprovaram antes de retomar

### 4. Assinatura com Múltiplos Signatários

**Problema:** Se documento tem múltiplos signatários, workflow deve continuar quando todos assinarem ou quando o primeiro assinar?

**Status atual:** `SignatureRequest.signers` armazena array, mas não há lógica de "todos devem assinar".

**Solução necessária:**
- Verificar se todos signatários assinaram antes de retomar
- Adicionar campo `signers_status` em `SignatureRequest` para rastrear quem assinou
- Retomar apenas quando todos assinarem (ou configurar comportamento)

**Arquivos a modificar:**
- `app/models/signature.py` - Adicionar rastreamento de status por signatário
- `app/routes/webhooks.py` - Verificar se todos assinaram antes de retomar

### 5. Timeout e Expiração

**Problema:** O que acontece se aprovação ou assinatura expirar?

**Status atual:**
- `WorkflowApproval` tem `expires_at` e `auto_approve_on_timeout`
- Mas não há job/task que verifica expirações automaticamente

**Solução necessária:**
- Criar job periódico (Celery/cron) que:
  1. Busca `WorkflowApproval` expiradas com `status = 'pending'`
  2. Se `auto_approve_on_timeout = true`, aprova automaticamente
  3. Se `auto_approve_on_timeout = false`, marca como `expired` e falha execução
- Similar para `SignatureRequest` expiradas

**Arquivos a criar/modificar:**
- `app/services/approval_service.py` - Função `check_expired_approvals()`
- `app/services/signature_service.py` - Função `check_expired_signatures()` (criar se não existir)
- Job scheduler (Celery task ou cron job)

### 6. Logs e Rastreamento Detalhado

**Status atual:**
- `WorkflowExecution` tem campos básicos: `status`, `error_message`, `execution_time_ms`
- `ExecutionContext.metadata.errors` armazena erros por node
- Logs via Python logging

**Falta:**
- Histórico de execução de cada node (quando iniciou, quando terminou, duração)
- Rastreamento de qual node está executando em tempo real
- Logs estruturados por node para debugging

**Solução necessária:**
- Adicionar tabela `WorkflowExecutionLog` ou campo JSONB `execution_logs` em `WorkflowExecution`
- Estrutura: `[{node_id, node_type, started_at, completed_at, duration_ms, status, error}]`
- Registrar cada node ao executar

**Arquivos a modificar:**
- `app/models/execution.py` - Adicionar `execution_logs` JSONB
- `app/services/workflow_executor.py` - Registrar logs de cada node

### 7. Execução Assíncrona

**Problema:** Execução atual é síncrona. Se workflow demorar muito, request HTTP pode timeout.

**Status atual:** Execução roda na mesma thread da request HTTP.

**Solução necessária:**
- Mover execução para background job (Celery, RQ, etc.)
- Endpoint retorna imediatamente com `execution_id`
- Cliente pode consultar status via polling ou WebSocket

**Arquivos a modificar:**
- Criar task Celery para `execute_workflow_async()`
- `app/routes/workflows.py` - Endpoint de execução retorna imediatamente

## Resumo: O Que Fazer

### Prioridade Alta

1. **Retomada automática após assinatura** - Workflow deve continuar quando documento for assinado
2. **Rastreamento de node atual** - Saber onde workflow pausou para retomar corretamente
3. **Múltiplas aprovações** - Definir comportamento (todos vs qualquer um)

### Prioridade Média

4. **Múltiplos signatários** - Verificar se todos assinaram antes de retomar
5. **Logs detalhados** - Histórico de execução por node
6. **Timeout/expiração** - Job para verificar e processar expirações

### Prioridade Baixa

7. **Execução assíncrona** - Mover para background jobs (melhora UX, mas não bloqueia)

## Pontos de Atenção

- **Estado do ExecutionContext:** Ao retomar, contexto deve estar exatamente como estava ao pausar
- **Idempotência:** Retomada não deve executar nodes já executados
- **Concorrência:** Se múltiplas aprovações simultâneas, garantir que retomada aconteça apenas uma vez
- **Erros na retomada:** Se retomada falhar, workflow deve ficar em estado consistente (não "paused" nem "running")

## Bugs Encontrados

### Bug no approval_service.py

**Problema:** Linha 31-36 de `app/services/approval_service.py` cria `ExecutionContext` incorretamente:
- Não passa `execution_id` (obrigatório no construtor)
- Tenta passar `metadata` como parâmetro (não aceito no construtor)

**Correção necessária:**
```python
context = ExecutionContext(
    workflow_id=str(workflow.id),
    execution_id=str(execution.id),  # ADICIONAR
    source_object_id=execution_context_data.get('source_object_id'),
    source_object_type=execution_context_data.get('source_object_type')
)
context.source_data = execution_context_data.get('source_data', {})  # ATRIBUIR DEPOIS
context.metadata = execution_context_data.get('metadata', {})  # ATRIBUIR DEPOIS
```
