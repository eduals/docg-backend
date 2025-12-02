# DocuGen - Plataforma de Geração Automatizada de Documentos

Backend Flask para uma plataforma SaaS de geração automatizada de documentos a partir de templates do Google Docs/Sheets, integrada com fontes de dados como HubSpot e com suporte opcional para assinatura eletrônica via ClickSign.

## 🎯 O que o projeto faz

O **DocuGen** é uma plataforma completa que permite:

- **Geração Automatizada de Documentos**: Cria documentos personalizados (Google Docs, Apresentações) a partir de templates, preenchendo automaticamente com dados de fontes externas
- **Workflows Configuráveis**: Define workflows que conectam fontes de dados (HubSpot) com templates do Google Drive para gerar documentos automaticamente
- **Mapeamento de Campos**: Sistema flexível de mapeamento que conecta propriedades de objetos (deals, contacts, companies) com tags nos templates
- **Integração com Google Workspace**: Autenticação OAuth e Service Account para acessar Google Drive, Docs e Sheets
- **Assinatura Eletrônica (Opcional)**: Integração com ClickSign para envio de documentos gerados para assinatura
- **Sistema Multi-tenant**: Suporte a múltiplas organizações com planos, limites e features opcionais
- **Segurança RISC**: Processamento de eventos de segurança do Google (Cross-Account Protection) para invalidar tokens quando necessário

## 🏗️ Arquitetura

### Componentes Principais

1. **Document Generation Service**: Orquestra a geração de documentos
   - Copia templates do Google Drive
   - Processa tags e substitui por dados reais
   - Gera PDFs automaticamente
   - Gerencia versões e histórico

2. **Workflow Engine**: Define e executa workflows de geração
   - Conecta fontes de dados com templates
   - Mapeia campos de dados para tags
   - Suporta triggers manuais e automáticos
   - Registra execuções e métricas

3. **Data Sources**: Conectores para fontes de dados
   - HubSpot (contacts, deals, companies, tickets, quotes)
   - Extensível para outras fontes (CRM, APIs, etc.)

4. **Template Management**: Gerenciamento de templates
   - Registro de templates do Google Drive
   - Detecção automática de tags
   - Versionamento de templates

5. **Integration Services**: Integrações opcionais
   - ClickSign (assinatura eletrônica)
   - Google OAuth e Service Account
   - RISC (Cross-Account Protection)

### Modelos de Dados Principais

- **Organization**: Organizações multi-tenant com planos e limites
- **User**: Usuários com roles e permissões
- **Template**: Templates do Google Drive com tags detectadas
- **Workflow**: Configurações de geração de documentos
- **GeneratedDocument**: Documentos gerados com histórico
- **DataSourceConnection**: Conexões criptografadas com fontes de dados
- **WorkflowExecution**: Logs de execução de workflows

## 🚀 Configuração Rápida

Para instruções detalhadas de setup, consulte [SETUP.md](./SETUP.md)

### Pré-requisitos

- Python 3.8+
- PostgreSQL 12+
- Conta Google (para OAuth e Google Drive)
- (Opcional) Conta ClickSign para assinatura eletrônica

### Instalação

1. **Instalar dependências:**
```bash
pip install -r requirements.txt
```

2. **Configurar variáveis de ambiente:**
```bash
cp env.example .env
# Editar .env com suas configurações
```

3. **Configurar banco de dados PostgreSQL e executar migrations:**
```bash
flask db init
flask db migrate -m "Initial migration"
flask db upgrade
```

4. **Rodar o servidor:**
```bash
python run.py
```

O servidor estará rodando em `http://localhost:5000`

## 📡 Principais Endpoints

### Documentos (API v1)

- `GET /api/v1/documents` - Lista documentos gerados
- `GET /api/v1/documents/<id>` - Detalhes de um documento
- `POST /api/v1/documents/generate` - Gera um novo documento
- `POST /api/v1/documents/<id>/regenerate` - Regenera um documento
- `DELETE /api/v1/documents/<id>` - Deleta um documento

### Workflows (API v1)

- `GET /api/v1/workflows` - Lista workflows
- `GET /api/v1/workflows/<id>` - Detalhes de um workflow
- `POST /api/v1/workflows` - Cria um novo workflow
- `PUT /api/v1/workflows/<id>` - Atualiza um workflow
- `DELETE /api/v1/workflows/<id>` - Deleta um workflow
- `POST /api/v1/workflows/<id>/activate` - Ativa um workflow

### Templates (API v1)

- `GET /api/v1/templates` - Lista templates
- `GET /api/v1/templates/<id>` - Detalhes de um template
- `POST /api/v1/templates` - Registra um novo template
- `POST /api/v1/templates/<id>/sync-tags` - Re-analisa tags do template
- `DELETE /api/v1/templates/<id>` - Deleta um template

### Conexões de Dados (API v1)

- `GET /api/v1/connections` - Lista conexões
- `GET /api/v1/connections/<id>` - Detalhes de uma conexão
- `POST /api/v1/connections` - Cria uma nova conexão
- `PUT /api/v1/connections/<id>` - Atualiza uma conexão
- `POST /api/v1/connections/<id>/test` - Testa uma conexão
- `DELETE /api/v1/connections/<id>` - Deleta uma conexão

### Organizações

- `GET /api/v1/organizations` - Lista organizações
- `GET /api/v1/organizations/<id>` - Detalhes de uma organização
- `POST /api/v1/organizations` - Cria uma nova organização

### Google OAuth

- `GET /api/v1/google-oauth/authorize` - Inicia fluxo OAuth (não requer organization_id no primeiro acesso)
- `GET /api/v1/google-oauth/callback` - Callback OAuth (cria Organization + User automaticamente se não existir)
- `GET /api/v1/google-oauth/status` - Status da conexão (requer organization_id)
- `POST /api/v1/google-oauth/disconnect` - Desconectar conta Google

**Fluxo de Primeiro Acesso:**
1. Usuário acessa `/api/v1/google-oauth/authorize` (sem organization_id)
2. Google redireciona para `/api/v1/google-oauth/callback`
3. Callback cria Organization + User admin automaticamente
4. Retorna `organization_id` para o frontend
5. Próximas chamadas já usam `organization_id`

**Nota:** O `hubspot_user_id` será NULL inicialmente e será preenchido quando o usuário instalar o app no HubSpot Marketplace.

### Google Drive

- `GET /api/google/drive/files` - Lista arquivos do Google Drive
- `GET /api/google/drive/folders` - Lista pastas do Google Drive

### ClickSign (Opcional)

- `POST /api/envelopes/create` - Cria envelope para assinatura
- `GET /api/envelopes/<id>/status` - Status do envelope

### RISC (Cross-Account Protection)

- `POST /api/risc/event` - Processa evento de segurança do Google

### Health Check

- `GET /api/health` - Status da API

## 🔐 Autenticação

A API utiliza autenticação baseada em tokens:

1. **Bearer Token**: Para autenticação de API
   ```
   Authorization: Bearer {BACKEND_API_TOKEN}
   ```

2. **JWT Tokens**: Para autenticação de usuários (via middleware `@require_auth`)

3. **Organization Context**: Middleware `@require_org` garante que requisições são feitas no contexto de uma organização

## 🔄 Fluxo de Geração de Documentos

1. **Configuração**:
   - Criar conexão com fonte de dados (ex: HubSpot)
   - Registrar template no Google Drive
   - Criar workflow conectando fonte → template
   - Configurar mapeamentos de campos

2. **Geração**:
   - Workflow busca dados do objeto na fonte (ex: deal do HubSpot)
   - Template é copiado no Google Drive
   - Tags no template são substituídas pelos dados mapeados
   - PDF é gerado automaticamente (se configurado)
   - Documento gerado é registrado no sistema

3. **Pós-processamento** (Opcional):
   - Envio para assinatura via ClickSign
   - Notificações
   - Webhooks

## 🔌 Integrações

### HubSpot
- Suporta objetos: contacts, deals, companies, tickets, quotes, line_items
- Busca propriedades e associações automaticamente
- Credenciais criptografadas no banco

### Google Workspace
- OAuth 2.0 para acesso ao Google Drive
- Service Account para operações em background
- Suporte a Google Docs e Google Slides
- Exportação automática para PDF

### ClickSign (Opcional)
- Criação de envelopes
- Upload de documentos
- Gerenciamento de signatários
- Webhooks de status

## 🛡️ Segurança

- **Criptografia**: Credenciais de conexões são criptografadas
- **RISC**: Processamento automático de eventos de segurança do Google
- **Multi-tenant**: Isolamento completo entre organizações
- **Permissões**: Sistema de roles e permissões por organização

## 📊 Recursos Multi-tenant

- **Planos**: free, starter, pro, enterprise
- **Limites**: Documentos mensais, usuários por organização
- **Features Opcionais**: ClickSign, integrações avançadas
- **Trial**: Período de teste configurável

## 🧪 Desenvolvimento

### Estrutura do Projeto

```
app/
├── models/          # Modelos de dados (SQLAlchemy)
├── routes/          # Rotas da API (Blueprints)
├── services/        # Lógica de negócio
│   ├── document_generation/  # Geração de documentos
│   ├── data_sources/        # Conectores de dados
│   └── integrations/        # Integrações externas
└── utils/           # Utilitários (auth, encryption, etc.)
```

### Migrations - Como Criar Tabelas Corretamente

**⚠️ IMPORTANTE: NUNCA crie tabelas diretamente no código Python usando `db.session.execute()` ou SQL raw. SEMPRE use Flask-Migrate para criar e modificar tabelas.**

#### Processo Correto para Criar uma Nova Tabela:

1. **Criar o Model SQLAlchemy** em `app/models/`:
   ```python
   # app/models/exemplo.py
   from datetime import datetime
   from app.database import db

   class Exemplo(db.Model):
       __tablename__ = 'exemplos'
       
       id = db.Column(db.Integer, primary_key=True)
       nome = db.Column(db.String(255), nullable=False)
       created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
       
       def __repr__(self):
           return f'<Exemplo {self.nome}>'
   ```

2. **Importar o Model em `app/models/__init__.py`**:
   ```python
   from .exemplo import Exemplo
   
   __all__ = [
       # ... outros models
       'Exemplo'
   ]
   ```

3. **Gerar a Migration**:
   ```bash
   flask db migrate -m "Add exemplos table"
   ```
   
   Isso cria um arquivo em `migrations/versions/` com o código SQLAlchemy para criar a tabela.

4. **Aplicar a Migration**:
   ```bash
   flask db upgrade
   ```
   
   Isso executa a migration e cria a tabela no banco de dados.

5. **Verificar se funcionou**:
   ```bash
   # Conectar ao PostgreSQL e verificar
   psql -U seu_usuario -d seu_banco
   \dt  # Lista todas as tabelas
   ```

#### Comandos Úteis:

```bash
# Criar nova migration (após modificar models)
flask db migrate -m "Descrição da mudança"

# Aplicar todas as migrations pendentes
flask db upgrade

# Reverter última migration
flask db downgrade

# Ver status das migrations
flask db current

# Ver histórico de migrations
flask db history
```

#### ❌ O QUE NÃO FAZER:

- ❌ **NÃO** criar tabelas com `db.session.execute(text("CREATE TABLE..."))` no código
- ❌ **NÃO** criar tabelas automaticamente em try/except quando não existem
- ❌ **NÃO** usar SQL raw para DDL (Data Definition Language)
- ❌ **NÃO** modificar tabelas diretamente no banco sem migration

#### ✅ O QUE FAZER:

- ✅ **SEMPRE** criar o model SQLAlchemy primeiro
- ✅ **SEMPRE** gerar migration com `flask db migrate`
- ✅ **SEMPRE** aplicar migration com `flask db upgrade`
- ✅ **SEMPRE** versionar migrations no Git
- ✅ **SEMPRE** testar migrations em ambiente de desenvolvimento antes de produção

#### Exemplo Completo: Criando Tabela PKCEVerifier

1. **Criar model** (`app/models/pkce.py`):
   ```python
   import uuid
   from datetime import datetime
   from app.database import db

   class PKCEVerifier(db.Model):
       __tablename__ = 'pkce_verifiers'
       
       state = db.Column(db.String(255), primary_key=True, nullable=False, index=True)
       code_verifier = db.Column(db.Text, nullable=False)
       expires_at = db.Column(db.DateTime, nullable=False, index=True)
       created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
   ```

2. **Importar em `app/models/__init__.py`**:
   ```python
   from .pkce import PKCEVerifier
   ```

3. **Gerar migration**:
   ```bash
   flask db migrate -m "Add PKCE verifiers table for OAuth"
   ```

4. **Aplicar migration**:
   ```bash
   flask db upgrade
   ```

**Pronto!** A tabela foi criada corretamente e está versionada.

## 📝 Notas

- O projeto evoluiu de um simples gerenciador de API keys do ClickSign para uma plataforma completa de geração de documentos
- Mantém compatibilidade com rotas legadas (`/api/account/*`) para integrações existentes
- Sistema de features permite habilitar/desabilitar funcionalidades por organização

## 📄 Licença

[Adicionar licença se aplicável]
