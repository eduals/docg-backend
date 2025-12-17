# Guia de Testes - Integração Temporal

Este documento descreve como testar a integração do Temporal para execução de workflows.

## Pré-requisitos

1. **Temporal Server rodando**
   - Local: `temporal server start-dev` (requer Docker)
   - Cloud: Configurar `TEMPORAL_ADDRESS` apontando para seu servidor

2. **Variáveis de Ambiente Configuradas**
   ```bash
   TEMPORAL_ADDRESS=localhost:7233
   TEMPORAL_NAMESPACE=default  # opcional
   TEMPORAL_TASK_QUEUE=docg-workflows  # opcional
   ```

3. **Worker Temporal em Execução**
   ```bash
   python -m app.temporal.worker
   ```

## Verificação de Configuração

Execute o script de verificação:

```bash
python scripts/verify_temporal.py
```

Este script verifica:
- ✅ Variáveis de ambiente configuradas
- ✅ Conectividade com Temporal Server
- ✅ Configuração do Worker

## Testes

### 1. Teste de Execução Básica

**Objetivo:** Verificar se um workflow simples é executado via Temporal.

**Passos:**

1. Criar um workflow simples com:
   - Trigger node (HubSpot)
   - Document node (Google Docs)

2. Executar workflow via API:
   ```bash
   curl -X POST http://localhost:5000/api/v1/hubspot/workflow-action \
     -H "Content-Type: application/json" \
     -d '{
       "object": {
         "objectId": "123",
         "objectType": "DEAL"
       },
       "inputFields": {
         "workflow_id": "uuid-do-workflow"
       }
     }'
   ```

3. Verificar no banco de dados:
   ```sql
   SELECT id, status, temporal_workflow_id, temporal_run_id 
   FROM workflow_executions 
   ORDER BY created_at DESC LIMIT 1;
   ```

4. Verificar no Temporal UI:
   - Acessar: http://localhost:8088
   - Procurar workflow com ID: `exec_{execution_id}`
   - Verificar status e histórico

**Resultado Esperado:**
- ✅ `temporal_workflow_id` preenchido no banco
- ✅ Workflow visível no Temporal UI
- ✅ Status mudando de `running` para `completed`

### 2. Teste de Signal de Aprovação

**Objetivo:** Verificar se signals de aprovação funcionam corretamente.

**Passos:**

1. Criar workflow com:
   - Trigger node
   - Document node
   - Approval node (human-in-loop)

2. Executar workflow (vai pausar no approval)

3. Verificar que execução está `paused`:
   ```sql
   SELECT status FROM workflow_executions WHERE id = 'execution_id';
   ```

4. Aprovar via API:
   ```bash
   curl -X POST http://localhost:5000/api/v1/approvals/{approval_token}/approve
   ```

5. Verificar que:
   - Signal foi enviado ao Temporal
   - Workflow retomou execução
   - Status mudou para `running` e depois `completed`

**Resultado Esperado:**
- ✅ Workflow pausa no approval node
- ✅ Signal é recebido pelo Temporal
- ✅ Workflow retoma após aprovação
- ✅ Execução completa com sucesso

### 3. Teste de Signal de Assinatura

**Objetivo:** Verificar se signals de assinatura funcionam corretamente.

**Passos:**

1. Criar workflow com:
   - Trigger node
   - Document node
   - Signature node

2. Executar workflow (vai pausar no signature)

3. Simular webhook de assinatura:
   ```bash
   curl -X POST http://localhost:5000/api/v1/webhooks/clicksign \
     -H "Content-Type: application/json" \
     -d '{
       "event": {
         "event_type": "document.signed",
         "envelope_id": "envelope-id"
       }
     }'
   ```

4. Verificar que:
   - Signal foi enviado ao Temporal
   - Workflow retomou execução
   - Status mudou para `completed`

**Resultado Esperado:**
- ✅ Workflow pausa no signature node
- ✅ Webhook envia signal ao Temporal
- ✅ Workflow retoma após assinatura
- ✅ Execução completa com sucesso

### 4. Teste de Timeout de Aprovação

**Objetivo:** Verificar se timeouts de aprovação funcionam.

**Passos:**

1. Criar workflow com approval node configurado com:
   - `timeout_hours: 1` (para teste rápido)
   - `auto_approve_on_timeout: true`

2. Executar workflow

3. Aguardar timeout (1 hora)

4. Verificar que:
   - Approval expirou
   - Workflow auto-aprovou (se configurado)
   - Execução continuou

**Resultado Esperado:**
- ✅ Approval expira após timeout
- ✅ Workflow auto-aprova (se configurado)
- ✅ Execução continua normalmente

### 5. Teste de Fallback (Temporal Desabilitado)

**Objetivo:** Verificar se fallback funciona quando Temporal não está disponível.

**Passos:**

1. Remover `TEMPORAL_ADDRESS` do `.env` ou definir como vazio

2. Executar workflow

3. Verificar que:
   - Workflow executa de forma síncrona
   - Logs mostram "usando execução síncrona"
   - Execução completa normalmente

**Resultado Esperado:**
- ✅ Sistema detecta que Temporal não está disponível
- ✅ Fallback para execução síncrona funciona
- ✅ Workflow executa normalmente

## Verificação de Logs

### Logs do Worker

O worker deve mostrar:
```
INFO - Conectando ao Temporal Server: localhost:7233
INFO - Conexão estabelecida com sucesso!
INFO - Worker iniciado na task queue: docg-workflows
INFO - Workflows registrados: DocGWorkflow
INFO - Activities registradas: 13
```

### Logs da API

Ao iniciar workflow via Temporal:
```
INFO - Workflow {workflow_id} iniciado via Temporal (execution: {execution_id})
```

### Logs do Workflow

No Temporal UI, você pode ver:
- Histórico completo de execução
- Activities executadas
- Signals recebidos
- Timeouts e retries

## Troubleshooting

### Worker não conecta

**Erro:** `Connection refused` ou `Failed to connect`

**Soluções:**
1. Verificar se Temporal Server está rodando: `temporal server start-dev`
2. Verificar `TEMPORAL_ADDRESS` está correto
3. Verificar firewall/network

### Workflow não inicia

**Erro:** Workflow não aparece no Temporal UI

**Soluções:**
1. Verificar se `TEMPORAL_ADDRESS` está configurado
2. Verificar logs da API para erros
3. Verificar se `start_workflow_execution()` está sendo chamado

### Signals não funcionam

**Erro:** Workflow não retoma após signal

**Soluções:**
1. Verificar se `temporal_workflow_id` está preenchido
2. Verificar logs do worker para erros
3. Verificar se signal name está correto (`approval_decision` ou `signature_update`)

### Activities falham

**Erro:** Activities falham com erro de contexto Flask

**Soluções:**
1. Verificar se worker está rodando com contexto Flask
2. Verificar se `current_app.app_context()` está sendo usado nas activities

## Comandos Úteis

### Iniciar Temporal Server (local)
```bash
temporal server start-dev
```

### Iniciar Worker
```bash
python -m app.temporal.worker
```

### Verificar configuração
```bash
python scripts/verify_temporal.py
```

### Ver workflows no Temporal UI
```bash
# Abrir navegador em:
http://localhost:8088
```

### Ver logs do worker
```bash
# Logs aparecem no console onde o worker está rodando
```

## Status da Implementação

- ✅ WorkflowExecutor integrado com Temporal
- ✅ Signals de aprovação implementados
- ✅ Signals de assinatura implementados
- ✅ Fallback para execução síncrona
- ✅ Script de verificação criado
- ✅ Documentação de testes criada
