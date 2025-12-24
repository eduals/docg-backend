# PipeHub - Plataforma de Automação de Documentos

> **Backend Flask** para automação end-to-end de geração de documentos, assinaturas digitais e workflows inteligentes.

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0.0-green.svg)](https://flask.palletsprojects.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-14%2B-blue.svg)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-8.4.0%2B-red.svg)](https://redis.io/)
[![Temporal](https://img.shields.io/badge/Temporal-Workflows-purple.svg)](https://temporal.io/)

---

## 🎯 O Que É o PipeHub?

**PipeHub** é uma plataforma SaaS de automação que conecta CRMs, gera documentos personalizados e coleta assinaturas digitais - tudo através de workflows visuais sem código.

### Principais Capacidades

1. **Extração de Dados Multi-Fonte**
   - HubSpot (Deals, Contacts, Companies, Tickets, Line Items)
   - Google Forms (respostas)
   - Webhooks customizados
   - Stripe (checkouts, subscriptions)

2. **Geração de Documentos Inteligente**
   - Google Docs/Slides com tags avançadas
   - Microsoft Word/PowerPoint
   - Sistema de templates com preview
   - Exportação automática para PDF

3. **Assinaturas Digitais**
   - ClickSign e ZapSign integrados
   - Tracking individual de signatários
   - Eventos real-time (viewed, signed, declined)
   - Lembretes automáticos

4. **Workflows Visuais Poderosos**
   - 14 apps modulares (Automatisch-style)
   - Branching condicional (if/else)
   - Aprovações humanas
   - Loops em tabelas de documentos

5. **Observabilidade Total**
   - SSE (Server-Sent Events) com replay
   - Logs estruturados consultáveis
   - Audit trail imutável
   - 12 estados de execução

---

## 🏗️ Arquitetura Moderna

### Stack Tecnológico

| Componente | Tecnologia | Propósito |
|------------|------------|-----------|
| **Backend** | Flask 3.0 | API REST + Blueprints |
| **Database** | PostgreSQL 14+ | Persistência com JSONB/UUID |
| **ORM** | SQLAlchemy 2.x | Modelagem declarativa |
| **Workflows** | Temporal.io | Orquestração assíncrona |
| **Real-time** | Redis Streams | SSE com replay de eventos |
| **Storage** | DigitalOcean Spaces | S3-compatible (documentos/PDFs) |
| **Auth** | JWT + OAuth 2.0 | Google, Microsoft, HubSpot |
| **Pagamentos** | Stripe | Checkout e webhooks |

### Apps Modulares (14 Apps)

Arquitetura inspirada no [Automatisch](https://github.com/automatisch/automatisch), onde cada app é um módulo independente com:

- **Actions** - Operações que o app pode executar
- **Triggers** - Eventos que iniciam workflows
- **Auth** - Configuração OAuth/API Key
- **Dynamic Data** - Dropdowns dinâmicos
- **Webhooks** - Callbacks de status

**Apps Disponíveis:**

| Categoria | Apps |
|-----------|------|
| **CRM** | HubSpot |
| **Documents** | Google Docs, Google Slides, Microsoft Word, Microsoft PowerPoint |
| **Storage** | Google Drive, Storage (S3) |
| **Email** | Gmail, Outlook |
| **Signature** | ClickSign, ZapSign |
| **Forms** | Google Forms |
| **AI** | OpenAI/LLMs |
| **Payment** | Stripe |

---

## 🚀 Features v2.2 (Production Ready)

### ✅ Execution v2.0 (14/14 Features)

| Feature | Descrição |
|---------|-----------|
| **Run State Unificado** | 12 estados de execução (running, paused, completed, failed, etc.) |
| **Preflight Checks** | Validação antes de executar (credenciais, templates, campos) |
| **SSE com Replay** | Eventos persistidos em Redis Streams |
| **Logs Estruturados** | Logs consultáveis por level/node/timestamp |
| **Audit Trail** | Rastreamento imutável para compliance |
| **Pause/Resume** | Controle manual de execuções |
| **Retry Inteligente** | Retry com backoff exponencial |
| **Rollback** | Reversão de execuções falhas |
| **Branching** | Caminhos condicionais (if/else) |
| **Human Approval** | Aprovações com timeout |
| **Datastore** | Key-value persistente por workflow |
| **Error Contexts** | Erros com contexto técnico + sugestões |
| **Progress Tracking** | Barra de progresso em tempo real |
| **Step Dependencies** | Dependências explícitas entre steps |

### ✅ Tags Avançadas v2.1

```handlebars
{{trigger.deal.amount | currency}}
{{trigger.contact.name | uppercase}}
{{IF trigger.deal.amount > 10000}}Premium{{ELSE}}Standard{{ENDIF}}
{{FOR item IN line_items}}{{item.name}} - {{item.price}}{{END FOR}}
```

**Pipes Disponíveis:** `uppercase`, `lowercase`, `currency`, `date`, `number`, `trim`, `replace`

**Condicionais:** `IF/ELSE/ENDIF` com operadores `>`, `<`, `==`, `!=`, `contains`

**Loops:** `FOR/END FOR` para duplicar linhas de tabela automaticamente

### ✅ Post-MVP v2.2

| Feature | Descrição |
|---------|-----------|
| **Dry-run** | Executa workflow sem persistir delivery/signature |
| **Until Phase** | Para execução em fase específica (preflight → trigger → render → save → delivery → signature) |
| **Signature Events SSE** | Eventos granulares: `signer.viewed`, `signer.signed`, `signer.declined`, `expired`, `completed` |
| **Loops em Google Docs** | Duplicação automática de linhas de tabela com `{{FOR item IN array}}` |

---

## 📋 Estrutura do Projeto

```
docg-backend/
├── app/
│   ├── models/                  # 10+ SQLAlchemy models
│   │   ├── organization.py      # Multi-tenant
│   │   ├── workflow.py          # Workflows + Nodes
│   │   ├── execution.py         # Run State v2.0
│   │   ├── execution_step.py    # Steps com error contexts
│   │   ├── execution_log.py     # Logs estruturados
│   │   ├── audit_event.py       # Audit trail
│   │   └── ...
│   │
│   ├── apps/                    # 14 apps modulares
│   │   ├── base.py              # BaseApp, ExecutionContext
│   │   ├── hubspot/
│   │   ├── google_docs/
│   │   ├── clicksign/
│   │   └── ...
│   │
│   ├── engine/                  # Workflow Engine
│   │   ├── engine.py            # Engine.run() - entry point
│   │   ├── steps/iterate.py     # Loop principal
│   │   ├── phases.py            # [v2.2] Fases de execução
│   │   └── ...
│   │
│   ├── temporal/                # Temporal.io
│   │   ├── workflows/           # DocGWorkflow
│   │   ├── activities/          # Activities
│   │   └── worker.py            # Worker principal
│   │
│   ├── services/
│   │   ├── document_generation/ # Loop parser, table loops
│   │   ├── sse_publisher.py     # Redis Streams SSE
│   │   └── ...
│   │
│   ├── tags/                    # [v2.1] Sistema de tags
│   │   ├── parser/              # Parser de sintaxe
│   │   └── engine/              # Avaliador
│   │
│   └── routes/                  # API Blueprints
│       ├── workflows.py
│       ├── signatures.py
│       ├── sse.py
│       └── ...
│
├── migrations/                  # Alembic migrations
├── tests/                       # Pytest tests
├── CLAUDE.md                    # 📚 Documentação arquitetural completa
└── requirements.txt
```

---

## 🔧 Setup Rápido

### Pré-requisitos

- Python 3.8+
- PostgreSQL 14+
- Redis 8.4.0+
- (Opcional) Temporal Server

### 1. Instalar Dependências

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configurar Variáveis de Ambiente

```bash
cp .env.example .env
# Editar .env com suas configurações
```

**Principais variáveis:**

```bash
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/pipehub

# Redis (SSE)
REDIS_URL=redis://localhost:6379/0

# Temporal (opcional)
TEMPORAL_ADDRESS=localhost:7233
TEMPORAL_NAMESPACE=default

# OAuth
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
HUBSPOT_CLIENT_ID=...
HUBSPOT_CLIENT_SECRET=...

# Encryption (AES-256)
ENCRYPTION_KEY=your-32-byte-key

# Storage (S3-compatible)
DO_SPACES_ACCESS_KEY=...
DO_SPACES_SECRET_KEY=...
DO_SPACES_BUCKET=pipehub
DO_SPACES_ENDPOINT=https://nyc3.digitaloceanspaces.com
```

### 3. Setup Database

```bash
# Criar database
createdb pipehub

# Aplicar migrations
flask db upgrade

# Verificar features
python verify_features.py
```

### 4. Rodar Servidor

```bash
# Servidor Flask
flask run

# Temporal Worker (opcional, em outro terminal)
python -m app.temporal.worker
```

**API disponível em:** `http://localhost:5000`

---

## 📡 Principais Endpoints

### Base URL: `/api/v1`

**Autenticação:**
```bash
Authorization: Bearer <JWT>
X-Organization-ID: <uuid>
```

### Workflows

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/workflows` | Listar workflows |
| POST | `/workflows` | Criar workflow |
| GET | `/workflows/{id}` | Detalhe do workflow |
| PUT | `/workflows/{id}` | Atualizar workflow |
| POST | `/workflows/{id}/activate` | Ativar workflow |
| POST | `/workflows/{id}/executions` | Executar workflow |
| GET | `/workflows/{id}/runs` | Histórico de execuções |

### Executions (v2.0)

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/executions/{id}` | Detalhe da execução |
| POST | `/executions/{id}/pause` | Pausar execução |
| POST | `/executions/{id}/resume` | Retomar execução |
| POST | `/executions/{id}/retry` | Retry (suporta `dry_run`, `until_phase`) |
| POST | `/executions/{id}/rollback` | Rollback |
| POST | `/executions/{id}/cancel` | Cancelar |
| GET | `/executions/{id}/logs` | Logs estruturados |
| GET | `/executions/{id}/audit` | Audit trail |

### Real-time (SSE)

```bash
GET /api/v1/sse/executions/{id}/stream

# Eventos:
# - step.started, step.completed, step.failed
# - execution.completed, execution.failed, execution.paused
# - signature.signer.viewed, signature.signer.signed, signature.signer.declined
# - signature.completed, signature.expired
```

### Tags (v2.1)

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| POST | `/workflows/{id}/tags/preview` | Preview de tags com dados reais |
| POST | `/workflows/{id}/tags/validate` | Validar sintaxe de tags |

### Signatures (v2.2)

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/signatures` | Listar assinaturas (com filtros) |
| GET | `/signatures/{id}` | Detalhe da assinatura |
| GET | `/signatures/{id}/signers` | Status detalhado de signatários |

### Templates

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/templates` | Listar templates |
| POST | `/templates/upload` | Upload de arquivo |
| POST | `/templates/{id}/sync-tags` | Re-analisar tags |

### Connections

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/connections` | Listar conexões OAuth/API |
| POST | `/connections` | Criar conexão |
| POST | `/connections/{id}/test` | Testar conexão |

---

## 🔄 Fluxo de Execução Completo

```
1. TRIGGER
   ├── Webhook recebido / HubSpot / Google Forms
   └── Extrai dados (deal, contact, form response, etc.)
       │
2. PREFLIGHT (v2.0)
   ├── Valida credenciais OAuth
   ├── Verifica se template existe
   └── Valida campos obrigatórios
       │
3. BRANCHING (v2.0)
   ├── Avalia condições ({{trigger.amount}} > 10000?)
   └── Escolhe próximo caminho
       │
4. RENDER (v2.1 + v2.2)
   ├── Copia template do Google Drive
   ├── Processa tags avançadas (pipes, condicionais)
   ├── Duplica linhas de tabela (loops)
   └── Substitui {{variáveis}} por dados reais
       │
5. APPROVAL (v2.0) - Opcional
   ├── Pausa execução
   ├── Envia notificação
   └── Aguarda decisão (approve/reject)
       │
6. SAVE
   ├── Exporta para PDF (se configurado)
   └── Salva no Google Drive/Storage
       │
7. DELIVERY
   ├── Envia por email (Gmail/Outlook)
   └── Anexa documento gerado
       │
8. SIGNATURE (v2.2)
   ├── Cria envelope (ClickSign/ZapSign)
   ├── Adiciona signatários
   ├── Envia para assinatura
   └── Emite eventos SSE granulares
       │
9. COMPLETION
   ├── Salva logs estruturados
   ├── Gera audit trail
   └── Emite evento SSE "execution.completed"
```

---

## 🎨 Exemplos de Uso

### 1. Gerar Proposta Comercial ao Fechar Deal (HubSpot)

```json
{
  "workflow": {
    "trigger": {
      "app": "hubspot",
      "event": "deal.updated",
      "conditions": {"dealstage": "closedwon"}
    },
    "steps": [
      {
        "app": "google-docs",
        "action": "copy-template",
        "parameters": {
          "template_id": "{{env.PROPOSAL_TEMPLATE_ID}}",
          "replacements": {
            "client_name": "{{trigger.deal.company.name}}",
            "deal_amount": "{{trigger.deal.amount | currency}}",
            "line_items": "{{trigger.deal.line_items}}"
          }
        }
      },
      {
        "app": "google-docs",
        "action": "export-pdf"
      },
      {
        "app": "clicksign",
        "action": "send-for-signature",
        "parameters": {
          "signers": ["{{trigger.deal.contact.email}}"]
        }
      }
    ]
  }
}
```

### 2. Dry-run com Until Phase (v2.2)

```bash
# Testar workflow até fase de render (sem enviar email/assinatura)
POST /api/v1/executions/{id}/retry
{
  "dry_run": true,
  "until_phase": "render"
}
```

### 3. Monitorar Assinatura em Real-time (v2.2)

```javascript
const eventSource = new EventSource(`/api/v1/sse/executions/${executionId}/stream`);

eventSource.addEventListener('signature.signer.viewed', (event) => {
  console.log('Signatário visualizou:', JSON.parse(event.data).signer_email);
});

eventSource.addEventListener('signature.signer.signed', (event) => {
  console.log('Signatário assinou:', JSON.parse(event.data));
});

eventSource.addEventListener('signature.completed', (event) => {
  console.log('Todos assinaram! Documento finalizado.');
  eventSource.close();
});
```

---

## 🧪 Testes

```bash
# Rodar todos os testes
pytest

# Testes da engine
pytest tests/engine/ -v

# Verificar features implementadas
python verify_features.py
```

---

## 🛡️ Segurança e Compliance

- **Criptografia AES-256** - Credenciais OAuth/API Keys em repouso
- **Multi-tenant Isolation** - Isolamento completo entre organizações
- **Audit Trail Imutável** - Rastreamento de todas as ações (compliance)
- **OAuth 2.0 + PKCE** - Fluxo seguro para Google, Microsoft, HubSpot
- **Role-Based Access** - Permissões granulares por organização
- **RISC (Cross-Account Protection)** - Processamento de eventos de segurança Google

---

## 📚 Documentação Adicional

| Arquivo | Descrição |
|---------|-----------|
| **[CLAUDE.md](./CLAUDE.md)** | 📖 Documentação arquitetural completa (1700+ linhas) |
| **[EXECUTION_FEATURES_PLAN.md](./EXECUTION_FEATURES_PLAN.md)** | Plano de features de execução |
| **[verify_features.py](./verify_features.py)** | Script de verificação de setup |

---

## 🗺️ Roadmap

### Próximas Features

- [ ] **F12: Workflow Templates** - Templates de workflows prontos (NDA, proposta, contrato)
- [ ] **F13: Scheduler** - Execuções agendadas (cron)
- [ ] **F14: Webhooks de Saída** - Notificar sistemas externos
- [ ] **Multi-idioma** - i18n para templates
- [ ] **UI Builder** - Editor visual de workflows (frontend)

---

## 🤝 Contribuindo

1. Fork o projeto
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

**Importante:**
- ✅ SEMPRE use migrations para mudanças no banco (`flask db migrate`)
- ✅ SEMPRE adicione testes para novas features
- ✅ SEMPRE atualize o CLAUDE.md com mudanças arquiteturais

---

## 📄 Licença

Proprietary - Todos os direitos reservados.

---

## 💬 Suporte

- **Documentação:** [CLAUDE.md](./CLAUDE.md)
- **Issues:** [GitHub Issues](https://github.com/seu-usuario/pipehub/issues)

---

**Versão:** 2.2 - Post-MVP Features
**Status:** ✅ Production Ready
**Última Atualização:** 23 de Dezembro de 2025
