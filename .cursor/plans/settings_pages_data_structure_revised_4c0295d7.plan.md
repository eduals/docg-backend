---
name: Settings Pages Data Structure Revised
overview: Plano revisado para estrutura de dados, layouts e endpoints das páginas de settings, baseado na análise do backend existente e removendo AI Agents e Integrations conforme solicitado.
todos:
  - id: create-backend-models
    content: "Criar modelos no backend: UserPreference, UserNotificationPreference, UserSession, LoginHistory, UserTwoFactorAuth, ApiKey, GlobalFieldMapping"
    status: completed
  - id: create-backend-endpoints-preferences
    content: Criar endpoints GET/PUT /users/me/preferences
    status: completed
  - id: create-backend-endpoints-notifications
    content: Criar endpoints GET/PUT /users/me/notification-preferences
    status: completed
  - id: create-backend-endpoints-security
    content: "Criar endpoints de segurança: sessions, login-history, 2FA, API keys"
    status: completed
  - id: implement-login-logging
    content: Implementar logging de login em auth.py para registrar no LoginHistory
    status: completed
  - id: implement-2fa-backend
    content: Implementar 2FA no backend usando pyotp (gerar secret, QR code, verificar código)
    status: completed
  - id: implement-api-keys-backend
    content: Implementar geração de API keys com prefixo dg_ e hash
    status: completed
  - id: create-frontend-account-page
    content: Criar página Account com formulário de edição de nome
    status: completed
  - id: create-frontend-preferences-page
    content: Criar página Preferences com formulário de preferências
    status: completed
  - id: create-frontend-notifications-page
    content: Criar página Notifications com toggles para tipos de email
    status: completed
  - id: create-frontend-security-page
    content: Criar página Security com sessões, login history, 2FA e API keys
    status: pending
  - id: create-frontend-mapping-fields-page
    content: Criar página Mapping Fields com lista e editor de mapeamentos globais
    status: pending
  - id: create-frontend-templates-page
    content: Criar página Templates com grid e ações CRUD
    status: pending
---

# Plano Revisado: Estrutura de Dados e Endpoints para Settings

## Análise do Backend Atual

### Modelos Existentes

- `Organization` - Já existe com campos: name, slug, plan, billing_email, etc.
- `User` - Já existe com campos: email, name, role, hubspot_user_id, google_user_id
- `DataSourceConnection` - Já existe para conexões OAuth (Google, Microsoft, HubSpot, etc.)
- `Template` - Já existe com endpoints completos
- `WorkflowFieldMapping` - Já existe, mas específico para workflows

### Endpoints Existentes

- `GET /organizations/me` - Retorna organização com limites e uso
- `PUT /organizations/{id}` - Atualiza nome e billing_email
- `GET /users/me` - Retorna usuário atual
- `PUT /users/{id}` - Atualiza nome e role
- `GET /settings` - Retorna configurações (Google Drive, ClickSign)
- `POST /settings` - Salva configurações
- `GET /templates` - Lista templates
- `GET/POST/PUT/DELETE /templates/{id}` - CRUD de templates

### O que NÃO existe

- Modelo para preferências de usuário
- Modelo para notificações por email
- Modelo para sessões/login history
- Modelo para 2FA
- Modelo para API keys
- Endpoints para preferências
- Endpoints para notificações
- Endpoints para segurança (sessões, 2FA, API keys)

## Estrutura de Dados por Página

### Account

#### 1. Account (`/settings/account`)

**Dados a exibir:**

- Nome da organização (do `Organization`)
- ID da organização
- Plano atual
- Data de criação
- Status (active/trial/expired)

**Dados a salvar:**

- Nome da organização

**Endpoints:**

- `GET /organizations/me` - Já existe
- `PUT /organizations/{id}` - Já existe (atualiza name)

**Layout:**

- Card com informações da organização
- Formulário para editar nome (Input + Button Save)
- Informações de plano (read-only, badge com cor por plano)
- Status da conta (badge)

**Componentes:**

- `OrganizationInfoCard` - Card com informações
- `OrganizationNameForm` - Formulário de edição

#### 2. Preferences (`/settings/preferences`)

**Dados a exibir:**

- Idioma preferido (pt, en, es)
- Formato de data (DD/MM/YYYY, MM/DD/YYYY, YYYY-MM-DD)
- Formato de hora (12h, 24h)
- Timezone
- Unidades (métricas/imperiais)

**Dados a salvar:**

- Todas as preferências acima

**Modelo a criar no backend:**

```python
class UserPreference(db.Model):
    __tablename__ = 'user_preferences'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False, unique=True)
    language = db.Column(db.String(10), default='pt')
    date_format = db.Column(db.String(20), default='DD/MM/YYYY')
    time_format = db.Column(db.String(10), default='24h')
    timezone = db.Column(db.String(100), default='America/Sao_Paulo')
    units = db.Column(db.String(20), default='metric')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

**Endpoints a criar:**

- `GET /users/me/preferences` - Retorna preferências do usuário
- `PUT /users/me/preferences` - Atualiza preferências

**Layout:**

- Seções: Idioma, Data/Hora, Unidades
- Select para idioma
- Select para formato de data
- Select para formato de hora
- Select para timezone
- Select para unidades
- Botão "Salvar" que salva todas as preferências

#### 3. Profile (`/settings/profile`)

**Status**: Já implementado

**Endpoints:**

- `GET /users/me` - Já existe
- `PUT /users/{id}` - Já existe

#### 4. Notifications (`/settings/notifications`)

**Dados a exibir:**

- Toggle: Receber emails
- Toggles individuais para cada tipo:
  - Documento gerado
  - Documento assinado
  - Workflow executado
  - Workflow não executado por completo

**Dados a salvar:**

- email_enabled (boolean)
- email_document_generated (boolean)
- email_document_signed (boolean)
- email_workflow_executed (boolean)
- email_workflow_failed (boolean)

**Modelo a criar no backend:**

```python
class UserNotificationPreference(db.Model):
    __tablename__ = 'user_notification_preferences'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False, unique=True)
    email_enabled = db.Column(db.Boolean, default=True)
    email_document_generated = db.Column(db.Boolean, default=True)
    email_document_signed = db.Column(db.Boolean, default=True)
    email_workflow_executed = db.Column(db.Boolean, default=True)
    email_workflow_failed = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

**Endpoints a criar:**

- `GET /users/me/notification-preferences` - Retorna preferências de notificação
- `PUT /users/me/notification-preferences` - Atualiza preferências

**Layout:**

- Toggle principal "Receber emails"
- Quando habilitado, mostra toggles individuais
- Quando desabilitado, todos os toggles individuais ficam desabilitados
- Botão "Salvar"

#### 5. Security & Access (`/settings/security`)

**Dados a exibir:**

- Sessões ativas (lista)
- Histórico de login (tabela)
- Status do 2FA (habilitado/desabilitado)
- API Keys (lista)

**Dados a salvar:**

- Habilitar/desabilitar 2FA
- Revogar sessões
- Criar/revogar API keys

**Modelos a criar no backend:**

```python
class UserSession(db.Model):
    __tablename__ = 'user_sessions'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False)
    session_token = db.Column(db.String(255), unique=True, nullable=False)  # Hash do token
    ip_address = db.Column(db.String(45))  # IPv6 suporta até 45 caracteres
    user_agent = db.Column(db.Text)
    last_activity = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime)
    
    # Index para busca rápida
    __table_args__ = (
        db.Index('idx_user_sessions_user_id', 'user_id'),
        db.Index('idx_user_sessions_token', 'session_token'),
    )

class LoginHistory(db.Model):
    __tablename__ = 'login_history'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    login_method = db.Column(db.String(50))  # 'oauth_google', 'oauth_microsoft', 'email', etc.
    success = db.Column(db.Boolean, default=True)
    failure_reason = db.Column(db.String(255))  # Se success=False
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Index para busca rápida
    __table_args__ = (
        db.Index('idx_login_history_user_id', 'user_id'),
        db.Index('idx_login_history_created_at', 'created_at'),
    )

class UserTwoFactorAuth(db.Model):
    __tablename__ = 'user_2fa'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False, unique=True)
    enabled = db.Column(db.Boolean, default=False)
    secret = db.Column(db.String(255))  # Secret para TOTP (criptografado)
    backup_codes = db.Column(JSONB)  # Códigos de backup (criptografados)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ApiKey(db.Model):
    __tablename__ = 'api_keys'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False)
    organization_id = db.Column(UUID(as_uuid=True), db.ForeignKey('organizations.id'), nullable=False)
    key_prefix = db.Column(db.String(10), nullable=False)  # 'dg_' prefix
    key_hash = db.Column(db.String(255), unique=True, nullable=False)  # Hash da chave completa
    name = db.Column(db.String(255))  # Nome descritivo dado pelo usuário
    last_used_at = db.Column(db.DateTime)
    expires_at = db.Column(db.DateTime, nullable=True)  # None = nunca expira
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Index
    __table_args__ = (
        db.Index('idx_api_keys_user_id', 'user_id'),
        db.Index('idx_api_keys_org_id', 'organization_id'),
    )
```

**Endpoints a criar:**

- `GET /users/me/sessions` - Lista sessões ativas
- `DELETE /users/me/sessions/{session_id}` - Revoga sessão
- `GET /users/me/login-history` - Histórico de login (com paginação)
- `GET /users/me/2fa` - Status do 2FA
- `POST /users/me/2fa/enable` - Habilita 2FA (gera secret e QR code)
- `POST /users/me/2fa/verify` - Verifica código e habilita
- `POST /users/me/2fa/disable` - Desabilita 2FA
- `GET /users/me/api-keys` - Lista API keys
- `POST /users/me/api-keys` - Cria nova API key (retorna chave completa apenas uma vez)
- `DELETE /users/me/api-keys/{key_id}` - Revoga API key

**Layout:**

- Seção "Sessões Ativas"
  - Lista de sessões com: dispositivo, IP, última atividade
  - Botão "Revogar" para cada sessão
  - Botão "Revogar todas as outras sessões"
- Seção "Histórico de Login"
  - Tabela: Data/Hora, IP, Método, Status
  - Paginação
- Seção "Autenticação de Dois Fatores"
  - Toggle para habilitar/desabilitar
  - Se habilitar: mostrar QR code, campo para código, botão verificar
  - Mostrar códigos de backup (apenas uma vez)
- Seção "API Keys"
  - Lista de keys: Nome, Prefixo (dg_xxx...), Último uso, Criado em
  - Botão "Criar nova API key"
  - Modal para criar: nome, expiração (opcional)
  - Ao criar: mostrar chave completa (apenas uma vez, copiar)
  - Botão "Revogar" para cada key

**Nota sobre Login History:**

- Registrar login em `auth.py` quando autenticação ocorre
- Registrar tentativas falhas
- Manter histórico por até 90 dias (conforme LGPD/GDPR)
- Não armazenar senhas ou tokens completos

#### 6. Connected Accounts (`/settings/connected-accounts`)

**Status**: Já resolvido

**Endpoints existentes:**

- `GET /connections` - Lista conexões (DataSourceConnection)
- `POST /connections/{type}/connect` - Conecta
- `DELETE /connections/{id}` - Desconecta

**Layout**: Já implementado em ConnectionsPage

### Features

#### 7. Mapping Fields (`/settings/mapping-fields`)

**Dados a exibir:**

- Mapeamentos globais de campos (não específicos de workflow)
- Templates de mapeamento salvos

**Dados a salvar:**

- Criar/editar/deletar mapeamentos globais
- Salvar como template

**Modelo a criar no backend:**

```python
class GlobalFieldMapping(db.Model):
    __tablename__ = 'global_field_mappings'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = db.Column(UUID(as_uuid=True), db.ForeignKey('organizations.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    source_system = db.Column(db.String(50), nullable=False)  # 'hubspot', 'google_drive', etc.
    target_system = db.Column(db.String(50), nullable=False)  # 'google_docs', 'microsoft_word', etc.
    mappings = db.Column(JSONB, nullable=False)  # Array de mapeamentos
    is_template = db.Column(db.Boolean, default=False)
    created_by = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

**Endpoints a criar:**

- `GET /field-mappings/global` - Lista mapeamentos globais
- `POST /field-mappings/global` - Cria mapeamento global
- `PUT /field-mappings/global/{id}` - Atualiza mapeamento
- `DELETE /field-mappings/global/{id}` - Deleta mapeamento
- `GET /field-mappings/templates` - Lista templates

**Layout:**

- Lista de mapeamentos globais
- Botão "Criar novo mapeamento"
- Editor similar ao de workflow (pode reutilizar componente)
- Opção "Salvar como template"
- Filtros por sistema origem/destino

#### 8. Templates (`/settings/templates`)

**Status**: Endpoints já existem

**Endpoints existentes:**

- `GET /templates` - Lista templates
- `GET /templates/{id}` - Detalhes do template
- `POST /templates` - Criar template (verificar se existe)
- `PUT /templates/{id}` - Atualizar template (verificar se existe)
- `DELETE /templates/{id}` - Deletar template (verificar se existe)
- `GET /templates/{id}/tags` - Tags do template
- `POST /templates/{id}/sync` - Sincronizar com Google Drive

**Layout:**

- Grid ou lista de templates
- Filtros por tipo (Google Docs, Word, PowerPoint, etc.)
- Busca
- Ações: criar, editar, deletar, sincronizar
- Cards com: nome, tipo, última modificação, tags

## Endpoints a Criar no Backend

### Prioridade Alta (Account)

1. `GET /users/me/preferences`
2. `PUT /users/me/preferences`
3. `GET /users/me/notification-preferences`
4. `PUT /users/me/notification-preferences`

### Prioridade Alta (Security)

5. `GET /users/me/sessions`
6. `DELETE /users/me/sessions/{session_id}`
7. `GET /users/me/login-history`
8. `GET /users/me/2fa`
9. `POST /users/me/2fa/enable`
10. `POST /users/me/2fa/verify`
11. `POST /users/me/2fa/disable`
12. `GET /users/me/api-keys`
13. `POST /users/me/api-keys`
14. `DELETE /users/me/api-keys/{key_id}`

### Prioridade Média (Features)

15. `GET /field-mappings/global`
16. `POST /field-mappings/global`
17. `PUT /field-mappings/global/{id}`
18. `DELETE /field-mappings/global/{id}`
19. `GET /field-mappings/templates`

## Modelos a Criar no Backend

1. `UserPreference` - Preferências do usuário
2. `UserNotificationPreference` - Preferências de notificação
3. `UserSession` - Sessões ativas
4. `LoginHistory` - Histórico de login
5. `UserTwoFactorAuth` - Configuração de 2FA
6. `ApiKey` - API keys do usuário
7. `GlobalFieldMapping` - Mapeamentos globais

## Implementação de 2FA

**Biblioteca recomendada**: `pyotp` para TOTP (Time-based One-Time Password)

**Fluxo:**

1. Usuário clica em "Habilitar 2FA"
2. Backend gera secret usando `pyotp.random_base32()`
3. Backend retorna secret e URL para QR code: `otpauth://totp/DocGen:{email}?secret={secret}&issuer=DocGen`
4. Frontend exibe QR code usando biblioteca como `qrcode.react`
5. Usuário escaneia e insere código
6. Backend verifica código com `pyotp.TOTP(secret).verify(code)`
7. Se válido, salva no banco e gera códigos de backup
8. Códigos de backup: array de 8-10 códigos aleatórios (criptografados)

## Geração de API Keys

**Formato**: `dg_{random_string}` (ex: `dg_a1b2c3d4e5f6...`)

**Processo:**

1. Gerar string aleatória (32-40 caracteres)
2. Prefixar com `dg_`
3. Criar hash (SHA-256) da chave completa
4. Salvar apenas hash no banco
5. Retornar chave completa apenas uma vez na criação
6. Frontend mostra modal com chave e botão "Copiar"
7. Usuário deve copiar imediatamente (não será mostrada novamente)

## Logging de Login

**Onde registrar:**

- Em `app/utils/auth.py` no decorator `require_auth` ou em rotas de login
- Registrar sucesso e falha
- Capturar IP e User-Agent do request
- Método de login: 'oauth_google', 'oauth_microsoft', 'email', 'api_key'

**Conformidade Legal:**

- Manter logs por até 90 dias (LGPD/GDPR)
- Não armazenar dados sensíveis
- Permitir exportação para auditoria
- Informar usuário sobre coleta de dados

## Ordem de Implementação

### Fase 1: Account (Mais simples)

1. Account - Usar endpoints existentes
2. Preferences - Criar modelo e endpoints
3. Notifications - Criar modelo e endpoints
4. Security - Criar modelos e endpoints (sessões, login history, 2FA, API keys)

### Fase 2: Features

5. Templates - Verificar endpoints e implementar UI
6. Mapping Fields - Criar modelo e endpoints globais

## Componentes Frontend a Criar

- `PreferencesForm` - Formulário de preferências
- `NotificationPreferencesForm` - Formulário de notificações
- `SessionsList` - Lista de sessões ativas
- `LoginHistoryTable` - Tabela de histórico
- `TwoFactorAuthSetup` - Setup de 2FA com QR code
- `ApiKeysList` - Lista de API keys
- `CreateApiKeyModal` - Modal para criar API key
- `GlobalFieldMappingsList` - Lista de mapeamentos globais
- `TemplatesGrid` - Grid de templates