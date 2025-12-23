# SSE Real-time Workflow Execution

Acompanhe a execucao de workflows em tempo real usando Server-Sent Events (SSE).

## Endpoint

```
GET /api/v1/sse/executions/{execution_id}/stream
```

## Autenticacao

### Via Headers (recomendado para clients que suportam)

```
Authorization: Bearer <jwt_token>
X-Organization-ID: <organization_uuid>
```

### Via Query Parameters (para EventSource nativo)

```
/api/v1/sse/executions/{id}/stream?Authorization=Bearer%20<token>&organization_id=<org_id>
```

## Exemplo de Uso (JavaScript)

```javascript
function subscribeToExecution(executionId, token, orgId) {
  // EventSource nao suporta headers customizados
  // Usar query params ou fetch com ReadableStream
  const url = `${API_URL}/api/v1/sse/executions/${executionId}/stream?Authorization=Bearer%20${token}&organization_id=${orgId}`;

  const eventSource = new EventSource(url);

  // Conexao estabelecida
  eventSource.addEventListener('connected', (event) => {
    console.log('Conectado:', JSON.parse(event.data));
  });

  // Step iniciou
  eventSource.addEventListener('step:started', (event) => {
    const data = JSON.parse(event.data);
    console.log(`Step ${data.data.node_type} iniciou`);
  });

  // Step completou
  eventSource.addEventListener('step:completed', (event) => {
    const data = JSON.parse(event.data);
    console.log(`Step ${data.data.node_type} completou em ${data.data.duration_ms}ms`);
  });

  // Step falhou
  eventSource.addEventListener('step:failed', (event) => {
    const data = JSON.parse(event.data);
    console.error(`Step ${data.data.node_type} falhou:`, data.data.error);
  });

  // Workflow completou
  eventSource.addEventListener('execution:completed', (event) => {
    const data = JSON.parse(event.data);
    console.log('Workflow concluido!', data);
    eventSource.close();
  });

  // Workflow falhou
  eventSource.addEventListener('execution:failed', (event) => {
    const data = JSON.parse(event.data);
    console.error('Workflow falhou:', data.data.error_message);
    eventSource.close();
  });

  // Workflow pausado (aguardando aprovacao/assinatura)
  eventSource.addEventListener('execution:paused', (event) => {
    const data = JSON.parse(event.data);
    console.log('Aguardando:', data.data.reason);
  });

  // Erro de conexao
  eventSource.onerror = (error) => {
    console.error('Erro SSE:', error);
    eventSource.close();
  };

  return eventSource;
}

// Uso
const stream = subscribeToExecution('abc-123', 'jwt-token', 'org-456');

// Desconectar
stream.close();
```

## React Hook

```typescript
import { useEffect, useState } from 'react';

interface ExecutionEvent {
  type: string;
  data: any;
  timestamp: string;
}

type StreamStatus = 'connecting' | 'connected' | 'completed' | 'failed' | 'disconnected';

export function useExecutionStream(executionId: string | null, token: string, orgId: string) {
  const [events, setEvents] = useState<ExecutionEvent[]>([]);
  const [status, setStatus] = useState<StreamStatus>('disconnected');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!executionId) return;

    setStatus('connecting');
    setEvents([]);
    setError(null);

    const url = `${process.env.REACT_APP_API_URL}/api/v1/sse/executions/${executionId}/stream?Authorization=Bearer%20${token}&organization_id=${orgId}`;
    const eventSource = new EventSource(url);

    eventSource.addEventListener('connected', () => {
      setStatus('connected');
    });

    const handleEvent = (type: string) => (e: MessageEvent) => {
      const data = JSON.parse(e.data);
      setEvents(prev => [...prev, { type, data, timestamp: data.timestamp }]);
    };

    eventSource.addEventListener('step:started', handleEvent('step:started'));
    eventSource.addEventListener('step:completed', handleEvent('step:completed'));
    eventSource.addEventListener('step:failed', handleEvent('step:failed'));

    eventSource.addEventListener('execution:completed', (e) => {
      handleEvent('execution:completed')(e);
      setStatus('completed');
      eventSource.close();
    });

    eventSource.addEventListener('execution:failed', (e) => {
      const data = JSON.parse(e.data);
      handleEvent('execution:failed')(e);
      setStatus('failed');
      setError(data.data?.error_message || 'Erro desconhecido');
      eventSource.close();
    });

    eventSource.addEventListener('execution:paused', handleEvent('execution:paused'));

    eventSource.onerror = () => {
      setStatus('disconnected');
      eventSource.close();
    };

    return () => eventSource.close();
  }, [executionId, token, orgId]);

  return { events, status, error };
}
```

## Estrutura dos Eventos

### connected

```json
{
  "execution_id": "uuid"
}
```

### step:started

```json
{
  "type": "step:started",
  "data": {
    "node_id": "uuid",
    "node_type": "google-docs",
    "status": "running",
    "started_at": "2024-01-15T10:30:00.000Z"
  },
  "timestamp": "2024-01-15T10:30:00.000Z"
}
```

### step:completed

```json
{
  "type": "step:completed",
  "data": {
    "node_id": "uuid",
    "node_type": "google-docs",
    "status": "success",
    "started_at": "2024-01-15T10:30:00.000Z",
    "completed_at": "2024-01-15T10:30:05.000Z",
    "output": {
      "document_id": "doc-uuid",
      "file_url": "https://..."
    }
  },
  "timestamp": "2024-01-15T10:30:05.000Z"
}
```

### step:failed

```json
{
  "type": "step:failed",
  "data": {
    "node_id": "uuid",
    "node_type": "signature",
    "status": "error",
    "started_at": "2024-01-15T10:30:05.000Z",
    "completed_at": "2024-01-15T10:30:10.000Z",
    "error": "Falha ao enviar para assinatura"
  },
  "timestamp": "2024-01-15T10:30:10.000Z"
}
```

### execution:completed

```json
{
  "type": "execution:completed",
  "data": {
    "execution_id": "uuid",
    "status": "completed",
    "execution_time_ms": 60000,
    "generated_document_id": "doc-uuid"
  },
  "timestamp": "2024-01-15T10:31:00.000Z"
}
```

### execution:failed

```json
{
  "type": "execution:failed",
  "data": {
    "execution_id": "uuid",
    "status": "failed",
    "error_message": "Template nao encontrado"
  },
  "timestamp": "2024-01-15T10:30:10.000Z"
}
```

### execution:paused

```json
{
  "type": "execution:paused",
  "data": {
    "execution_id": "uuid",
    "reason": "approval"
  },
  "timestamp": "2024-01-15T10:30:30.000Z"
}
```

## Health Check

```
GET /api/v1/sse/health
```

Resposta:

```json
{
  "status": "healthy",
  "redis": "connected"
}
```

## Fallback para Polling

Se SSE nao estiver disponivel, use o endpoint de polling:

```
GET /api/v1/workflows/{workflow_id}/runs/{execution_id}?include_logs=true
```

## Configuracao NGINX

```nginx
location /api/v1/sse/ {
    proxy_pass http://backend;
    proxy_http_version 1.1;
    proxy_set_header Connection "";
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 86400s;
}
```

## Configuracao Gunicorn

Para suportar conexoes longas SSE, use workers async:

```bash
gunicorn -w 4 -k gevent run:app
```

## Variavel de Ambiente

```
REDIS_URL=redis://localhost:6379/0
```
