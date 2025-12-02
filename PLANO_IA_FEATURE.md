# Plano de Implementação: Feature de IA Multi-Provedor para Geração de Textos

## Visão Geral

Implementar sistema que permite usar múltiplos provedores de IA (OpenAI, Google Gemini, Anthropic, e outros) para gerar trechos de texto automaticamente em documentos. O usuário define tags no formato `{{ai:paragrapho1}}` no template do Google Docs e configura no workflow quais campos do HubSpot serão usados para gerar cada texto, além de escolher o provedor e modelo de IA.

---

## Arquitetura: LiteLLM como Wrapper Unificado ✅

> **Decisão**: Usar **LiteLLM** como única biblioteca de IA. Não serão criadas classes separadas por provedor (OpenAIService, GeminiService, etc). LiteLLM abstrai 100+ modelos com interface única.

### Benefícios:
- Menos código para manter
- Interface unificada para todos os provedores
- Suporte automático a novos modelos
- Retry logic e error handling embutidos
- Formato de modelo: `provider/model` (ex: `openai/gpt-4`, `gemini/gemini-1.5-pro`)

---

## Componentes Principais

### 1. Serviço de IA Unificado (LiteLLM)

- **Arquivo**: `app/services/ai/llm_service.py` (novo)
- Classe `LLMService` que encapsula LiteLLM
- Interface única para todos os provedores

```python
class LLMService:
    def generate_text(
        self,
        model: str,           # Ex: "openai/gpt-4", "gemini/gemini-1.5-pro"
        prompt: str,
        api_key: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        timeout: int = 60,
        **kwargs
    ) -> LLMResponse:
        """Gera texto usando LiteLLM"""
        
    def validate_api_key(
        self,
        provider: str,
        api_key: str
    ) -> bool:
        """Valida se API key é válida fazendo chamada teste"""
```

### 2. Utilitários e Helpers

- **Arquivo**: `app/services/ai/utils.py` (novo)
- Funções para validar modelos suportados via LiteLLM
- Normalizar nomes de provedores
- Listar provedores e modelos disponíveis
- Validar formato de modelo
- Helper para custo estimado por modelo

```python
SUPPORTED_PROVIDERS = ['openai', 'gemini', 'anthropic']
PROVIDER_MODELS = {
    'openai': ['gpt-4', 'gpt-4-turbo', 'gpt-3.5-turbo'],
    'gemini': ['gemini-1.5-pro', 'gemini-1.5-flash'],
    'anthropic': ['claude-3-opus', 'claude-3-sonnet', 'claude-3-haiku']
}

def get_model_string(provider: str, model: str) -> str:
    """Retorna string de modelo para LiteLLM (ex: openai/gpt-4)"""
    
def get_available_providers() -> list:
    """Lista provedores disponíveis"""
    
def get_available_models(provider: str) -> list:
    """Lista modelos disponíveis para um provedor"""
    
def estimate_cost(provider: str, model: str, tokens: int) -> float:
    """Estima custo baseado em tokens"""
```

### 3. Modelo de Dados: AIGenerationMapping

- **Arquivo**: `app/models/workflow.py`
- Criar modelo `AIGenerationMapping` similar a `WorkflowFieldMapping`

```python
class AIGenerationMapping(db.Model):
    __tablename__ = 'ai_generation_mappings'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id = db.Column(UUID(as_uuid=True), db.ForeignKey('workflows.id'), nullable=False)
    
    # Tag e configuração
    ai_tag = db.Column(db.String(255), nullable=False)  # Ex: "paragrapho1"
    source_fields = db.Column(JSONB)  # Array de campos HubSpot
    
    # Provedor e modelo
    provider = db.Column(db.String(50), nullable=False)  # 'openai', 'gemini', etc
    model = db.Column(db.String(100), nullable=False)    # 'gpt-4', 'gemini-pro', etc
    ai_connection_id = db.Column(UUID(as_uuid=True), db.ForeignKey('data_source_connections.id'))
    
    # Configuração do prompt
    prompt_template = db.Column(db.Text)  # Template com placeholders {{field}}
    temperature = db.Column(db.Float, default=0.7)
    max_tokens = db.Column(db.Integer, default=1000)
    
    # Fallback (se IA falhar)
    fallback_value = db.Column(db.Text)  # Valor padrão se geração falhar
    
    # Métricas de uso (para auditoria/debugging)
    last_used_at = db.Column(db.DateTime)
    usage_count = db.Column(db.Integer, default=0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Índices
    __table_args__ = (
        db.UniqueConstraint('workflow_id', 'ai_tag', name='unique_workflow_ai_tag'),
        db.Index('idx_ai_mapping_connection', 'ai_connection_id'),
    )
    
    # Relationships
    ai_connection = db.relationship('DataSourceConnection', foreign_keys=[ai_connection_id])
    
    def to_dict(self):
        return {
            'id': str(self.id),
            'workflow_id': str(self.workflow_id),
            'ai_tag': self.ai_tag,
            'source_fields': self.source_fields,
            'provider': self.provider,
            'model': self.model,
            'ai_connection_id': str(self.ai_connection_id) if self.ai_connection_id else None,
            'prompt_template': self.prompt_template,
            'temperature': self.temperature,
            'max_tokens': self.max_tokens,
            'fallback_value': self.fallback_value,
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None,
            'usage_count': self.usage_count,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
```

### 4. Atualização do Modelo Workflow

- **Arquivo**: `app/models/workflow.py`
- Adicionar relationship para ai_mappings

```python
class Workflow(db.Model):
    # ... campos existentes ...
    
    # Adicionar este relationship:
    ai_mappings = db.relationship(
        'AIGenerationMapping', 
        backref='workflow', 
        lazy='dynamic', 
        cascade='all, delete-orphan'
    )
    
    def to_dict(self, include_mappings=False, include_ai_mappings=False):
        result = {
            # ... campos existentes ...
        }
        
        if include_mappings:
            result['field_mappings'] = [m.to_dict() for m in self.field_mappings]
        
        # Adicionar:
        if include_ai_mappings:
            result['ai_mappings'] = [m.to_dict() for m in self.ai_mappings]
        
        return result
```

### 5. Atualização do Models __init__.py

- **Arquivo**: `app/models/__init__.py`
- Exportar o novo modelo

```python
from .workflow import Workflow, WorkflowFieldMapping, AIGenerationMapping

__all__ = [
    # ... existentes ...
    'AIGenerationMapping',
]
```

### 6. Armazenamento de API Keys (BYOK)

- **Arquivo**: `app/models/connection.py`
- Usar `DataSourceConnection` existente para armazenar credenciais de IA
- Tipos suportados: 'openai', 'gemini', 'anthropic'
- Usar criptografia existente (`app/utils/encryption.py`)

> **Nota**: Não é necessário criar AIDataSource seguindo o padrão BaseDataSource, pois os provedores de IA não são fontes de dados no sentido tradicional (não puxamos dados deles, apenas enviamos prompts).

### 7. Processamento de Tags AI

- **Arquivo**: `app/services/document_generation/tag_processor.py`
- Estender `TagProcessor` para detectar tags `{{ai:...}}`

```python
class TagProcessor:
    AI_TAG_PATTERN = r'\{\{ai:([^}]+)\}\}'
    
    def extract_ai_tags(self, content: str) -> list[str]:
        """Retorna lista de nomes de tags AI encontradas"""
        matches = re.findall(self.AI_TAG_PATTERN, content)
        return list(set(matches))
    
    async def process_ai_tag(
        self,
        tag_name: str,
        mapping: AIGenerationMapping,
        source_data: dict,
        llm_service: LLMService
    ) -> str:
        """
        Processa uma tag AI:
        1. Coleta valores dos campos mapeados
        2. Monta prompt usando template
        3. Chama serviço de IA
        4. Retorna texto gerado ou fallback
        """
```

### 8. Integração no Fluxo de Geração

- **Arquivo**: `app/services/document_generation/generator.py`
- Modificar `DocumentGenerator.generate_from_workflow()`:

```python
async def generate_from_workflow(self, workflow, source_data: dict) -> GeneratedDocument:
    # 1. Buscar template
    template_content = self.get_template_content(workflow.template)
    
    # 2. Detectar tags AI no template
    ai_tags = self.tag_processor.extract_ai_tags(template_content)
    
    # 3. Processar tags AI primeiro
    ai_metrics = AIGenerationMetrics()
    for tag_name in ai_tags:
        mapping = self.get_ai_mapping(workflow, tag_name)
        if mapping:
            start_time = time.time()
            try:
                generated_text = await self.process_ai_tag(mapping, source_data)
                template_content = self.replace_tag(template_content, f"ai:{tag_name}", generated_text)
                ai_metrics.add_success(mapping, time.time() - start_time)
            except AIGenerationError as e:
                # Usar fallback ou manter tag
                fallback = mapping.fallback_value or f"[Erro: {tag_name}]"
                template_content = self.replace_tag(template_content, f"ai:{tag_name}", fallback)
                ai_metrics.add_failure(mapping, str(e))
    
    # 4. Processar tags normais
    # ... código existente ...
    
    # 5. Salvar métricas de IA no execution
    self.save_ai_metrics(execution, ai_metrics)
```

### 9. Integração com WorkflowExecution

- **Arquivo**: `app/models/execution.py`
- Adicionar campo para métricas de IA

```python
class WorkflowExecution(db.Model):
    # ... campos existentes ...
    
    # Adicionar:
    ai_metrics = db.Column(JSONB)  # Métricas de geração de IA
    
    # Estrutura do ai_metrics:
    # {
    #     "total_tags": 3,
    #     "successful": 2,
    #     "failed": 1,
    #     "total_time_ms": 4500,
    #     "total_tokens": 1200,
    #     "estimated_cost_usd": 0.024,
    #     "details": [
    #         {
    #             "tag": "paragrapho1",
    #             "provider": "openai",
    #             "model": "gpt-4",
    #             "time_ms": 2100,
    #             "tokens": 800,
    #             "status": "success"
    #         },
    #         ...
    #     ]
    # }
```

---

## Rotas/Endpoints

### Conexões de IA (em `app/routes/connections.py`)

```python
# Criar/atualizar conexão de IA
POST /api/v1/connections/ai
Body: { 
    "organization_id": "uuid",
    "provider": "openai",  # openai, gemini, anthropic
    "api_key": "sk-...",
    "name": "OpenAI Principal"  # opcional
}

# Listar conexões de IA da organização
GET /api/v1/organizations/<org_id>/connections/ai

# Obter conexão específica
GET /api/v1/connections/ai/<connection_id>

# Atualizar conexão
PATCH /api/v1/connections/ai/<connection_id>
Body: { "api_key": "sk-new...", "name": "Novo nome" }

# Deletar conexão
DELETE /api/v1/connections/ai/<connection_id>

# ⚠️ NOVO: Testar conexão (validar API key)
POST /api/v1/connections/ai/<connection_id>/test
Response: { "valid": true, "provider": "openai", "message": "API key válida" }
```

### Mapeamentos de IA (em `app/routes/workflows.py`)

```python
# Criar mapeamento de IA
POST /api/v1/workflows/<workflow_id>/ai-mappings
Body: {
    "ai_tag": "paragrapho1",
    "source_fields": ["dealname", "amount", "company.name"],
    "provider": "openai",
    "model": "gpt-4",
    "ai_connection_id": "uuid",
    "prompt_template": "Gere um parágrafo descrevendo o deal {{dealname}} no valor de {{amount}} para a empresa {{company.name}}",
    "temperature": 0.7,
    "max_tokens": 500,
    "fallback_value": "[Texto não gerado]"
}

# Listar mapeamentos do workflow
GET /api/v1/workflows/<workflow_id>/ai-mappings

# Obter mapeamento específico
GET /api/v1/workflows/<workflow_id>/ai-mappings/<mapping_id>

# Atualizar mapeamento
PATCH /api/v1/workflows/<workflow_id>/ai-mappings/<mapping_id>

# Deletar mapeamento
DELETE /api/v1/workflows/<workflow_id>/ai-mappings/<mapping_id>
```

### Rotas Auxiliares de IA (em `app/routes/ai_routes.py` - novo)

```python
# Listar provedores disponíveis
GET /api/v1/ai/providers
Response: [
    { "id": "openai", "name": "OpenAI", "models": ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo"] },
    { "id": "gemini", "name": "Google Gemini", "models": ["gemini-1.5-pro", "gemini-1.5-flash"] },
    { "id": "anthropic", "name": "Anthropic", "models": ["claude-3-opus", "claude-3-sonnet"] }
]

# Listar modelos de um provedor
GET /api/v1/ai/providers/<provider>/models
Response: ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo"]
```

---

## Migração de Banco de Dados

- **Arquivo**: `migrations/versions/xxx_add_ai_generation_tables.py`

```python
def upgrade():
    # Criar tabela ai_generation_mappings
    op.create_table(
        'ai_generation_mappings',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('workflow_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('workflows.id'), nullable=False),
        sa.Column('ai_tag', sa.String(255), nullable=False),
        sa.Column('source_fields', postgresql.JSONB),
        sa.Column('provider', sa.String(50), nullable=False),
        sa.Column('model', sa.String(100), nullable=False),
        sa.Column('ai_connection_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('data_source_connections.id')),
        sa.Column('prompt_template', sa.Text),
        sa.Column('temperature', sa.Float, default=0.7),
        sa.Column('max_tokens', sa.Integer, default=1000),
        sa.Column('fallback_value', sa.Text),
        sa.Column('last_used_at', sa.DateTime),
        sa.Column('usage_count', sa.Integer, default=0),
        sa.Column('created_at', sa.DateTime, default=datetime.utcnow),
        sa.Column('updated_at', sa.DateTime, default=datetime.utcnow),
    )
    
    # Índices
    op.create_unique_constraint('unique_workflow_ai_tag', 'ai_generation_mappings', ['workflow_id', 'ai_tag'])
    op.create_index('idx_ai_mapping_connection', 'ai_generation_mappings', ['ai_connection_id'])
    
    # Adicionar coluna ai_metrics em workflow_executions
    op.add_column('workflow_executions', sa.Column('ai_metrics', postgresql.JSONB))

def downgrade():
    op.drop_column('workflow_executions', 'ai_metrics')
    op.drop_table('ai_generation_mappings')
```

---

## Registro de Blueprint

- **Arquivo**: `app/__init__.py`
- Adicionar registro do novo blueprint

```python
def create_app(config_class=Config):
    # ... código existente ...
    
    # Adicionar após outras rotas:
    from app.routes import ai_routes
    app.register_blueprint(ai_routes.ai_bp)
    
    return app
```

---

## Tratamento de Erros e Fallback

### Estratégia de Erro

```python
class AIGenerationError(Exception):
    """Erro genérico de geração de IA"""
    
class AITimeoutError(AIGenerationError):
    """Timeout na chamada de IA"""
    
class AIQuotaExceededError(AIGenerationError):
    """Quota de API excedida"""
    
class AIInvalidKeyError(AIGenerationError):
    """API key inválida"""

# No generator.py:
async def process_ai_tag(self, mapping, source_data):
    try:
        result = await self.llm_service.generate_text(
            model=f"{mapping.provider}/{mapping.model}",
            prompt=self.build_prompt(mapping, source_data),
            api_key=self.get_api_key(mapping.ai_connection),
            temperature=mapping.temperature,
            max_tokens=mapping.max_tokens,
            timeout=60  # 60 segundos timeout
        )
        return result.text
    except AITimeoutError:
        logger.warning(f"Timeout na geração AI para tag {mapping.ai_tag}")
        return mapping.fallback_value or "[Timeout na geração]"
    except AIQuotaExceededError:
        logger.error(f"Quota excedida para provider {mapping.provider}")
        raise  # Propagar para interromper documento
    except AIInvalidKeyError:
        logger.error(f"API key inválida para connection {mapping.ai_connection_id}")
        raise  # Propagar para interromper documento
    except Exception as e:
        logger.error(f"Erro inesperado na geração AI: {e}")
        return mapping.fallback_value or f"[Erro: {mapping.ai_tag}]"
```

### Comportamento de Fallback

1. **Timeout**: Usa `fallback_value` se definido, senão `[Timeout na geração]`
2. **Quota Excedida**: Interrompe documento, marca execution como `failed`
3. **API Key Inválida**: Interrompe documento, marca execution como `failed`
4. **Outros Erros**: Usa `fallback_value` se definido, senão `[Erro: tag_name]`

---

## Logging e Auditoria

### Configuração de Logging

```python
# app/services/ai/llm_service.py
import logging

logger = logging.getLogger('docugen.ai')

class LLMService:
    async def generate_text(self, ...):
        logger.info(f"[AI] Iniciando geração - provider={provider}, model={model}")
        start_time = time.time()
        
        try:
            result = await litellm.acompletion(...)
            duration_ms = (time.time() - start_time) * 1000
            
            logger.info(
                f"[AI] Geração concluída - provider={provider}, model={model}, "
                f"tokens={result.usage.total_tokens}, time_ms={duration_ms:.0f}"
            )
            return result
            
        except Exception as e:
            logger.error(
                f"[AI] Erro na geração - provider={provider}, model={model}, "
                f"error={type(e).__name__}: {str(e)}"
            )
            raise
```

### Auditoria por Organização

- Atualizar `usage_count` e `last_used_at` no mapping após cada uso
- Salvar métricas detalhadas em `WorkflowExecution.ai_metrics`
- Considerar tabela separada para histórico de uso (futuro)

---

## Processamento Assíncrono (Celery)

### Decisão: Síncrono dentro do Fluxo Existente

O processamento de tags AI será **síncrono** dentro da task Celery existente de geração de documentos, pois:

1. O documento já é gerado em background via Celery
2. Tags AI são parte do mesmo fluxo de geração
3. Não faz sentido criar sub-tasks para cada tag

### Timeout e Retry

```python
# Em tasks.py (se existir) ou generator.py
@celery.task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    time_limit=300  # 5 minutos limite total
)
def generate_document_task(self, workflow_id, source_data):
    try:
        # ... geração com tags AI ...
    except AIQuotaExceededError as e:
        # Não retry para quota excedida
        raise
    except AITimeoutError as e:
        # Retry automático para timeout
        raise self.retry(exc=e)
```

---

## Fluxo de Execução Completo

1. Usuário cria template com tag `{{ai:paragrapho1}}`
2. Usuário configura conexão de IA (salva API key da OpenAI, por exemplo)
3. Usuário configura workflow e cria mapeamento de IA:
   - Tag: `paragrapho1`
   - Campos: `dealname`, `amount`, `company.name`
   - Provider: `openai`, Model: `gpt-4`
   - Prompt: "Gere um parágrafo descrevendo..."
   - Fallback: "[Texto não disponível]"
4. Ao gerar documento (manual ou via trigger):
   - Sistema detecta tag `{{ai:paragrapho1}}`
   - Busca mapeamento no workflow
   - Busca conexão do provedor configurado
   - Coleta valores dos campos HubSpot mapeados
   - Monta prompt com esses valores
   - Chama LiteLLM com timeout de 60s
   - Substitui tag pelo texto gerado (ou fallback)
   - Registra métricas no execution
5. Continua processamento normal das outras tags
6. Salva documento final

---

## Arquivos a Criar

| Arquivo | Descrição |
|---------|-----------|
| `app/services/ai/__init__.py` | Package init |
| `app/services/ai/llm_service.py` | Serviço unificado com LiteLLM |
| `app/services/ai/utils.py` | Helpers e validações |
| `app/services/ai/exceptions.py` | Classes de exceção customizadas |
| `app/routes/ai_routes.py` | Rotas auxiliares de IA |
| `migrations/versions/xxx_add_ai_generation_tables.py` | Migração de banco |

## Arquivos a Modificar

| Arquivo | Modificação |
|---------|-------------|
| `app/models/workflow.py` | Adicionar `AIGenerationMapping` e relationship |
| `app/models/__init__.py` | Exportar `AIGenerationMapping` |
| `app/models/execution.py` | Adicionar campo `ai_metrics` |
| `app/services/document_generation/tag_processor.py` | Detectar e processar tags AI |
| `app/services/document_generation/generator.py` | Integrar geração de IA |
| `app/routes/connections.py` | Endpoints para conexões de IA |
| `app/routes/workflows.py` | Endpoints CRUD para ai-mappings |
| `app/__init__.py` | Registrar blueprint `ai_routes` |
| `requirements.txt` | Adicionar `litellm>=1.50.0` |

---

## Dependências

```txt
# requirements.txt - Adicionar apenas:
litellm>=1.50.0
```

> ⚠️ **Nota**: NÃO adicionar `openai`, `google-generativeai`, `anthropic` individualmente. LiteLLM instala as dependências necessárias automaticamente quando o provedor é usado.

---

## Ordem de Implementação

### Fase 1: Fundação (3 tasks)
1. [x] Adicionar `litellm>=1.50.0` ao `requirements.txt`
2. [x] Criar migração para tabela `ai_generation_mappings` e coluna `ai_metrics`
3. [x] Criar modelo `AIGenerationMapping` e atualizar `Workflow` com relationship

### Fase 2: Serviço de IA (2 tasks)
4. [x] Criar `app/services/ai/llm_service.py` com `LLMService`
5. [x] Criar `app/services/ai/utils.py` com helpers e `app/services/ai/exceptions.py`

### Fase 3: Processamento (2 tasks)
6. [x] Estender `TagProcessor` para detectar tags `{{ai:...}}`
7. [x] Atualizar `DocumentGenerator` para processar tags AI com métricas

### Fase 4: Rotas (3 tasks)
8. [x] Adicionar endpoints de conexões de IA em `app/routes/connections.py` (incluindo `/test`)
9. [x] Adicionar endpoints CRUD para ai-mappings em `app/routes/workflows.py`
10. [x] Criar `app/routes/ai_routes.py` com rotas auxiliares (providers/models)

### Fase 5: Integração (2 tasks)
11. [x] Registrar blueprint `ai_routes` em `app/__init__.py`
12. [x] Atualizar `app/models/__init__.py` para exportar `AIGenerationMapping`

### Fase 6: Qualidade (2 tasks)
13. [x] Implementar logging estruturado em `LLMService`
14. [x] Criar testes unitários e de integração

---

## Considerações Técnicas

| Aspecto | Implementação |
|---------|---------------|
| **Arquitetura** | LiteLLM como única dependência de IA |
| **Segurança** | API keys criptografadas via `app/utils/encryption.py` |
| **Rate Limiting** | Usar retry logic embutido do LiteLLM |
| **Error Handling** | Exceções customizadas + fallback por tag |
| **Custos** | Métricas de tokens salvos no execution |
| **Cache** | Considerar para v2 (prompt hash como chave) |
| **Timeout** | 60s por chamada, 300s limite total |
| **Logging** | Logger dedicado `docugen.ai` |
| **Auditoria** | `usage_count` + `ai_metrics` em execution |

---

## Status do Plano

📋 **Total de Tasks**: 14  
✅ **Completadas**: 14/14 (100%)  
🎉 **Status**: IMPLEMENTAÇÃO CONCLUÍDA!

