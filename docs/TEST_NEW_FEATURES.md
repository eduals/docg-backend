# Testing Guide - Execution v2.0 Features

> **Status:** All features implemented and migrations applied
> **Date:** 2025-12-23

## ✅ Pre-flight Checks

- [x] Migrations applied successfully (4 migrations)
- [x] Flask app starts without errors
- [x] All new endpoints registered
- [x] Redis connected and Streams working
- [x] Environment variables configured

## Features Implemented

### F1: Run State Unificado ✅
**Status:** Implemented
**Database:** `workflow_executions` table updated with 10+ new fields
- `progress` (0-100)
- `current_step` (JSONB)
- `last_error_human` / `last_error_tech`
- `preflight_summary` (JSONB)
- `delivery_state` / `signature_state`
- `recommended_actions` (JSONB)
- `phase_metrics` (JSONB)
- `correlation_id` (UUID)

**Testing:**
```bash
# Run a workflow execution and check the new fields
curl -X POST http://localhost:5000/api/v1/workflows/{workflow_id}/executions \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Organization-ID: $ORG_ID" \
  -H "Content-Type: application/json" \
  -d '{"trigger_data": {...}}'

# Check execution status with new fields
curl -X GET http://localhost:5000/api/v1/executions/{execution_id} \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Organization-ID: $ORG_ID"
```

**Expected Response:**
```json
{
  "id": "uuid",
  "status": "running",
  "progress": 45,
  "current_step": {
    "index": 2,
    "label": "Generate Document",
    "node_id": "uuid",
    "node_type": "action"
  },
  "last_error_human": null,
  "last_error_tech": null,
  "correlation_id": "uuid",
  "phase_metrics": {
    "preflight": {"start": "...", "end": "...", "duration_ms": 150}
  }
}
```

### F2: Preflight Check ✅
**Status:** Implemented
**Files:**
- `app/temporal/activities/preflight.py`
- `app/controllers/api/v1/executions/preflight.py`
- `app/services/recommended_actions.py`

**Endpoints:**
- `POST /api/v1/workflows/{workflow_id}/preflight` - Validate before execution
- `GET /api/v1/executions/{execution_id}/preflight` - Get preflight results

**Testing:**
```bash
# Run preflight check before execution
curl -X POST http://localhost:5000/api/v1/workflows/{workflow_id}/preflight \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Organization-ID: $ORG_ID" \
  -H "Content-Type: application/json" \
  -d '{"trigger_data": {"deal_id": "123"}}'
```

**Expected Response:**
```json
{
  "can_execute": true,
  "blocking": [],
  "warnings": [
    {
      "code": "template.large_file",
      "domain": "template",
      "message_human": "Template maior que 10MB pode demorar",
      "message_tech": "Template size: 15MB",
      "node_id": "uuid",
      "severity": "warning"
    }
  ],
  "recommended_actions": [],
  "groups": {
    "template": [...]
  }
}
```

**Validation Domains:**
- `data` - Required fields present in trigger_data
- `template` - Template exists and accessible
- `permissions` - OAuth tokens valid and permissions granted
- `delivery` - Email/storage configuration valid
- `signature` - Signature provider configured

### F3: SSE Schema v1 Padronizado ✅
**Status:** Implemented
**Files:**
- `app/services/sse_publisher.py` (complete rewrite)
- `app/routes/sse.py` (updated)

**Schema v1 Format:**
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

**Event Types:**
- `execution.created`
- `execution.status_changed`
- `execution.progress`
- `preflight.completed`
- `step.started`
- `step.completed`
- `step.failed`
- `execution.completed`
- `execution.failed`
- `execution.canceled`
- `signature.requested`
- `signature.completed`

### F4: SSE com Replay (Redis Streams) ✅
**Status:** Implemented
**Technology:** Redis Streams (XADD, XREAD)

**Configuration:**
- `REDIS_STREAM_MAXLEN=1000` - Keep last 1000 events per stream
- `REDIS_STREAM_TTL=86400` - Stream expires after 24 hours

**Testing:**
```bash
# Connect to SSE stream
curl -N -H "Authorization: Bearer $TOKEN" \
  -H "X-Organization-ID: $ORG_ID" \
  http://localhost:5000/api/v1/sse/executions/{execution_id}/stream

# Reconnect with Last-Event-ID for replay
curl -N -H "Authorization: Bearer $TOKEN" \
  -H "X-Organization-ID: $ORG_ID" \
  -H "Last-Event-ID: 1234567890-0" \
  http://localhost:5000/api/v1/sse/executions/{execution_id}/stream
```

**How Replay Works:**
1. Client disconnects at event ID `1234567890-0`
2. Client reconnects with `Last-Event-ID: 1234567890-0` header
3. Server sends all events **after** that ID from Redis Stream
4. Client receives missed events, then continues with real-time stream

**Health Check:**
```bash
curl http://localhost:5000/api/v1/sse/health
```

**Expected Response:**
```json
{
  "status": "healthy",
  "redis": "connected",
  "mode": "streams"
}
```

### F5: Logs Estruturados ✅
**Status:** Implemented
**Database:** `execution_logs` table created
**Service:** `app/services/execution_logger.py`

**Endpoint:** `GET /api/v1/executions/{execution_id}/logs`

**Testing:**
```bash
curl -X GET "http://localhost:5000/api/v1/executions/{execution_id}/logs?level=error&domain=step&limit=50" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Organization-ID: $ORG_ID"
```

**Query Parameters:**
- `level` - Filter by level: `ok`, `warn`, `error`
- `domain` - Filter by domain: `preflight`, `step`, `delivery`, `signature`
- `step_id` - Filter by specific step UUID
- `limit` - Results per page (default: 50, max: 100)
- `cursor` - UUID for pagination

**Expected Response:**
```json
{
  "logs": [
    {
      "id": "uuid",
      "execution_id": "uuid",
      "step_id": "uuid",
      "timestamp": "2025-12-23T10:30:00.000Z",
      "level": "error",
      "domain": "step",
      "message_human": "Erro ao gerar documento",
      "message_tech": "Template not found: uuid",
      "correlation_id": "uuid"
    }
  ],
  "has_more": false,
  "next_cursor": null
}
```

**Log Levels:**
- `ok` - Success operations
- `warn` - Non-blocking issues
- `error` - Failures

**Log Domains:**
- `preflight` - Validation checks
- `step` - Step execution
- `delivery` - Email/storage delivery
- `signature` - Signature requests

### F6: Auditoria Append-Only ✅
**Status:** Implemented
**Database:** `audit_events` table created
**Service:** `app/services/audit_service.py`

**Endpoint:** `GET /api/v1/executions/{execution_id}/audit`

**Testing:**
```bash
curl -X GET "http://localhost:5000/api/v1/executions/{execution_id}/audit?limit=50" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Organization-ID: $ORG_ID"
```

**Expected Response:**
```json
{
  "events": [
    {
      "id": "uuid",
      "organization_id": "uuid",
      "timestamp": "2025-12-23T10:30:00.000Z",
      "actor_type": "user",
      "actor_id": "user@example.com",
      "action": "execution.started",
      "target_type": "execution",
      "target_id": "uuid",
      "metadata": {
        "workflow_name": "Contract Generation",
        "trigger_source": "hubspot"
      }
    }
  ],
  "has_more": false,
  "next_cursor": null
}
```

**Audit Actions:**
- `execution.started`
- `execution.canceled`
- `execution.retried`
- `execution.resumed`
- `execution.completed`
- `execution.failed`
- `document.generated`
- `document.saved`
- `document.sent`
- `signature.requested`
- `signature.signed`
- `signature.declined`
- `signature.expired`
- `template.version_updated`

**Actor Types:**
- `user` - User-initiated action
- `system` - System/Temporal action
- `webhook` - External webhook trigger

**Important Note:**
⚠️ The `metadata` field is stored as `event_metadata` in the database (SQLAlchemy reserved word), but exposed as `metadata` in the API.

### F7: Error Contexts ✅
**Status:** Implemented
**Database:** `execution_steps` table updated
- Added `error_human` (TEXT) - User-friendly error message
- Added `error_tech` (TEXT) - Technical error details

**Endpoint:** `GET /api/v1/executions/{execution_id}/steps`

**Testing:**
```bash
curl -X GET http://localhost:5000/api/v1/executions/{execution_id}/steps \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Organization-ID: $ORG_ID"
```

**Expected Response:**
```json
{
  "steps": [
    {
      "id": "uuid",
      "execution_id": "uuid",
      "node_id": "uuid",
      "step_index": 2,
      "status": "failure",
      "error_human": "Não foi possível gerar o documento. Verifique se o template existe.",
      "error_tech": "TemplateNotFoundError: Template ID 'uuid' not found in organization",
      "data_in": {...},
      "data_out": null,
      "started_at": "2025-12-23T10:30:00.000Z",
      "completed_at": "2025-12-23T10:30:05.000Z"
    }
  ]
}
```

**Error Message Separation:**
- `error_human` - Shown to end users, actionable, translated
- `error_tech` - For developers, includes stack traces, error codes

### F10: Pause/Resume, Cancel, Retry ✅
**Status:** Implemented
**Files:**
- `app/controllers/api/v1/executions/control.py`
- `app/temporal/workflows/docg_workflow.py` (new signals)

**Endpoints:**
- `POST /api/v1/executions/{execution_id}/resume`
- `POST /api/v1/executions/{execution_id}/cancel`
- `POST /api/v1/executions/{execution_id}/retry`

**Testing Resume:**
```bash
# Workflow pauses at needs_review state
# Resume with user decision
curl -X POST http://localhost:5000/api/v1/executions/{execution_id}/resume \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Organization-ID: $ORG_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "approved": true,
    "changes": {"recipient_email": "new@example.com"}
  }'
```

**Testing Cancel:**
```bash
curl -X POST http://localhost:5000/api/v1/executions/{execution_id}/cancel \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Organization-ID: $ORG_ID" \
  -H "Content-Type: application/json" \
  -d '{"reason": "User requested cancellation"}'
```

**Testing Retry:**
```bash
# Retry a failed execution
curl -X POST http://localhost:5000/api/v1/executions/{execution_id}/retry \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Organization-ID: $ORG_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "trigger_data": {...},
    "from_step": 3
  }'
```

**Temporal Signals:**
- `resume_after_review` - Sends user decision to paused workflow
- `cancel` - Gracefully cancels running workflow

### F12: Endpoints Adicionais ✅
**Status:** Implemented

All endpoints documented above plus:
- Health checks
- Pagination support
- Filtering by multiple criteria
- Cursor-based pagination

## Database Schema

### New Tables

#### `execution_logs`
```sql
CREATE TABLE execution_logs (
    id UUID PRIMARY KEY,
    execution_id UUID REFERENCES workflow_executions(id),
    step_id UUID REFERENCES execution_steps(id) NULL,
    timestamp TIMESTAMP NOT NULL,
    level VARCHAR(10) NOT NULL,  -- ok, warn, error
    domain VARCHAR(50) NOT NULL,  -- preflight, step, delivery, signature
    message_human TEXT NOT NULL,
    message_tech TEXT,
    correlation_id UUID NOT NULL,
    INDEX idx_logs_execution (execution_id),
    INDEX idx_logs_level (level),
    INDEX idx_logs_domain (domain),
    INDEX idx_logs_timestamp (timestamp)
);
```

#### `audit_events`
```sql
CREATE TABLE audit_events (
    id UUID PRIMARY KEY,
    organization_id UUID REFERENCES organizations(id),
    timestamp TIMESTAMP NOT NULL,
    actor_type VARCHAR(20) NOT NULL,  -- user, system, webhook
    actor_id VARCHAR(255),
    action VARCHAR(100) NOT NULL,
    target_type VARCHAR(50) NOT NULL,
    target_id UUID NOT NULL,
    event_metadata JSONB,  -- Note: 'metadata' is reserved in SQLAlchemy
    INDEX idx_audit_org_target (organization_id, target_type, target_id),
    INDEX idx_audit_timestamp (timestamp),
    INDEX idx_audit_action (action)
);
```

### Updated Tables

#### `workflow_executions`
Added fields:
- `progress` INTEGER DEFAULT 0
- `current_step` JSONB
- `last_error_human` TEXT
- `last_error_tech` TEXT
- `preflight_summary` JSONB
- `delivery_state` VARCHAR(20)
- `signature_state` VARCHAR(20)
- `recommended_actions` JSONB
- `phase_metrics` JSONB
- `correlation_id` UUID

#### `execution_steps`
Added fields:
- `error_human` TEXT
- `error_tech` TEXT

## Integration Testing Checklist

### Manual Testing

- [ ] Start Flask app: `flask run`
- [ ] Create a new workflow execution
- [ ] Monitor SSE stream: `curl -N http://localhost:5000/api/v1/sse/executions/{id}/stream`
- [ ] Check execution status with new fields
- [ ] View execution logs: `GET /api/v1/executions/{id}/logs`
- [ ] View audit events: `GET /api/v1/executions/{id}/audit`
- [ ] Run preflight check before execution
- [ ] Test SSE reconnection with Last-Event-ID header
- [ ] Pause and resume an execution
- [ ] Cancel a running execution
- [ ] Retry a failed execution

### Automated Testing

Create integration tests for:
```python
# tests/integration/test_execution_v2.py

def test_execution_with_run_state(client, auth_headers):
    """Test execution creates proper run state"""

def test_preflight_check(client, auth_headers):
    """Test preflight validation"""

def test_sse_stream_with_replay(client, auth_headers):
    """Test SSE reconnection and replay"""

def test_execution_logs(client, auth_headers):
    """Test structured logging"""

def test_audit_trail(client, auth_headers):
    """Test audit event creation"""

def test_pause_resume_flow(client, auth_headers):
    """Test pause/resume with Temporal signals"""
```

## Troubleshooting

### Common Issues

1. **Redis Connection Error**
   ```
   Error: Redis connection failed
   ```
   **Solution:**
   - Check Redis is running: `redis-cli ping`
   - Verify `REDIS_URL` in .env

2. **SSE Stream Not Working**
   ```
   Error: Stream not found
   ```
   **Solution:**
   - Ensure execution exists and belongs to organization
   - Check Redis Streams: `redis-cli XINFO STREAM docg:exec:{execution_id}`

3. **Preflight Check Errors**
   ```
   Error: Cannot validate workflow
   ```
   **Solution:**
   - Ensure workflow has nodes configured
   - Check that trigger_data matches workflow requirements

4. **SQLAlchemy Reserved Word Error**
   ```
   Error: Attribute name 'metadata' is reserved
   ```
   **Solution:**
   - Use `event_metadata` in model, expose as `metadata` in API
   - See: CLAUDE.md "Erros Comuns e Soluções" section

## Next Steps (Optional Post-MVP)

### F9: Dry-run & Until Phase
- [ ] Add `dry_run` parameter to execution endpoint
- [ ] Add `until_phase` for partial execution
- [ ] Implement phase-based execution control

### F11: Signature Improvements
- [ ] Add signature expiration tracking
- [ ] Implement signature event webhooks
- [ ] Add signer-specific tracking

### F13: Correlation ID Propagation
- [ ] Add correlation_id to all HTTP requests
- [ ] Implement distributed tracing headers
- [ ] Add to Temporal activity context

### F14: Phase Metrics Enhancement
- [ ] Add per-step timing metrics
- [ ] Implement performance alerts
- [ ] Create metrics dashboard

## Performance Considerations

### Redis Streams Cleanup

The current implementation keeps:
- Last 1000 events per stream (MAXLEN)
- 24-hour TTL per stream

Consider implementing a cleanup job:
```python
# Clean up old streams
for key in redis.scan_iter("docg:exec:*"):
    # Check if execution is older than 7 days
    # Delete stream if expired
```

### Database Indexes

All critical queries are indexed:
- `execution_logs`: execution_id, level, domain, timestamp
- `audit_events`: organization_id + target_type + target_id, timestamp, action

Monitor query performance with:
```sql
EXPLAIN ANALYZE SELECT * FROM execution_logs WHERE execution_id = '...';
```

## Documentation Updated

- [x] CLAUDE.md updated to v2.0
- [x] All new features documented
- [x] API endpoints documented
- [x] Database schema documented
- [x] Error handling documented

---

**Implementation Date:** 2025-12-23
**Migrations Applied:** 4/4
**Status:** ✅ Ready for Testing
