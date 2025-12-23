# Plano: Sistema Avançado de Tags + HubSpot Expandido + Multi-CRM

> **Data:** 23 de Dezembro de 2025
> **Status:** Planejamento
> **Prioridade:** Tags Avançadas primeiro

---

## Resumo Executivo

Implementar um sistema de tags avançado (formatação, fórmulas, condicionais, loops) com preview, expandir suporte ao HubSpot (Tickets, Line Items, Associações) e preparar arquitetura Multi-CRM.

**Decisões:**
- Sintaxe: Estilo Pipe (`{{value | format:"DD/MM/YYYY"}}`)
- Prioridade: Tags Avançadas → HubSpot Expandido → Multi-CRM
- Preview: Necessário antes de gerar documento
- Triggers HubSpot: Os atuais são suficientes (new-contact, new-deal, updated-deal)

---

## 1. Situação Atual

### Sistema de Tags (compute_parameters.py)

| Feature | Status | Localização |
|---------|--------|-------------|
| `{{trigger.field}}` | ✅ | `app/engine/compute_parameters.py` |
| `{{step.id.field}}` | ✅ | `app/engine/compute_parameters.py` |
| `{{flow.field}}` | ✅ | `app/engine/compute_parameters.py` |
| `{{now}}`, `{{uuid}}` | ✅ | `app/engine/compute_parameters.py` |
| Replace em docs | ✅ | `app/apps/*/actions/replace_tags.py` |
| `{{ai:tag}}` | ✅ | `app/apps/ai/actions/process_tags.py` |

### HubSpot (app/apps/hubspot/)

| Objeto | Status | Observação |
|--------|--------|------------|
| Contacts | ✅ Completo | CRUD + triggers |
| Deals | ✅ Completo | CRUD + triggers |
| Companies | ⚠️ Parcial | Leitura via API |
| Tickets | ⚠️ Parcial | Leitura via API (scope: `tickets`) |
| Line Items | ⚠️ Parcial | Leitura via associações (scope: `e-commerce`) |
| Associações | ❌ | Não exposto nas tags |

### Fontes de Dados Existentes

| Fonte | Normalização | Localização |
|-------|--------------|-------------|
| HubSpot | `source: 'hubspot'` | `app/engine/trigger/process.py` |
| Webhook | `source: 'webhook'` | `app/engine/trigger/process.py` |
| Google Forms | `source: 'google_forms'` | `app/apps/google_forms/triggers/` |
| ClickSign | `source: 'clicksign'` | `app/apps/clicksign/webhooks/` |
| ZapSign | `source: 'zapsign'` | `app/apps/zapsign/webhooks/` |
| Stripe | `source: 'stripe'` | `app/apps/stripe/webhooks/` |

---

## 2. O Que Implementar

### 2.1 Tags Avançadas (PRIORIDADE 1)

#### A) Formatação de Datas

```
{{trigger.deal.closedate | format:"DD/MM/YYYY"}}
{{trigger.deal.createdate | format:"MMMM YYYY"}}
{{trigger.deal.closedate | format:"DD de MMMM de YYYY, HH:mm"}}
```

**Formatos:**
- `DD`, `MM`, `YYYY`, `YY` - dia, mês, ano
- `HH`, `mm`, `ss` - hora, minuto, segundo
- `MMMM` - mês por extenso
- `dddd` - dia da semana
- Locale: `pt-BR`, `en-US`

#### B) Fórmulas Matemáticas

```
{{= trigger.deal.amount * 1.1}}
{{= ROUND(trigger.deal.amount, 2)}}
{{= SUM(trigger.deal.line_items.amount)}}
{{= AVG(trigger.deal.line_items.price)}}
{{= IF(trigger.deal.amount > 10000, "Enterprise", "Standard")}}
```

**Funções:** `SUM`, `ROUND`, `AVG`, `MIN`, `MAX`, `ABS`, `IF`

#### C) Manipulação de Texto

```
{{trigger.contact.firstname | upper}}
{{trigger.contact.email | lower}}
{{trigger.contact.firstname | capitalize}}
{{trigger.deal.description | truncate:100}}
{{trigger.contact.firstname | concat:" " | concat:trigger.contact.lastname}}
```

**Transforms:** `upper`, `lower`, `capitalize`, `truncate`, `concat`

#### D) Formatação de Números/Moeda

```
{{trigger.deal.amount | currency:"BRL"}}
{{trigger.deal.amount | currency:"USD"}}
{{trigger.deal.amount | number:2}}
```

#### E) Condicionais em Bloco

```
{{IF trigger.deal.amount > 50000}}
Você se qualifica para desconto de 10%!
{{ELSE}}
Entre em contato para negociar descontos.
{{ENDIF}}
```

**Operadores:** `==`, `!=`, `>`, `<`, `>=`, `<=`, `~` (contém), `&&`, `||`

#### F) Loops

```
{{FOR item IN trigger.deal.line_items}}
- {{item.name}}: {{item.quantity}} x {{item.price | currency:"BRL"}}
{{ENDFOR}}
```

#### G) Tags Globais

```
{{$timestamp}}           # ISO timestamp da geração
{{$date}}                # Data atual YYYY-MM-DD
{{$date_br}}             # Data atual DD/MM/YYYY
{{$time}}                # Hora atual HH:MM
{{$document_number}}     # Número sequencial
{{$uuid}}                # UUID aleatório
{{$workflow_name}}       # Nome do workflow
```

### 2.2 Preview de Tags (PRIORIDADE 1)

**Endpoint:** `POST /api/v1/workflows/{id}/tags/preview`

**Request:**
```json
{
  "object_type": "deal",
  "object_id": "123456",
  "template_id": "uuid"
}
```

**Response:**
```json
{
  "tags": [
    {"tag": "{{trigger.deal.amount | currency:\"BRL\"}}", "resolved": "R$ 50.000,00", "status": "ok"},
    {"tag": "{{trigger.deal.custom}}", "resolved": null, "status": "warning", "message": "Campo não encontrado"}
  ],
  "loops": [{"tag": "{{FOR item IN line_items}}", "items_count": 3, "sample": [...]}],
  "conditionals": [{"tag": "{{IF amount > 50000}}", "result": true, "branch": "true"}],
  "warnings": ["Campo 'custom' não encontrado"],
  "errors": [],
  "sample_output": "Texto de exemplo com tags resolvidas..."
}
```

### 2.3 HubSpot Expandido (PRIORIDADE 2)

#### A) Tickets

**Actions:**
- `create-ticket` - Criar ticket
- `update-ticket` - Atualizar ticket
- `get-ticket` - Buscar ticket

**Propriedades:** `subject`, `content`, `priority`, `status`, `hs_pipeline_stage`, `hs_ticket_priority`

**Scope OAuth:** `tickets` (NÃO `crm.objects.tickets`)

#### B) Line Items

**Actions:**
- `get-line-items` - Buscar line items de um deal
- `create-line-item` - Criar line item em deal

**Propriedades:** `name`, `price`, `quantity`, `amount`, `hs_sku`, `discount`

**Scope OAuth:** `e-commerce` (NÃO `crm.objects.line_items`)

#### C) Sistema de Associações

Permitir buscar objetos relacionados para usar nas tags:

```
{{trigger.deal.associated.contacts[0].firstname}}
{{trigger.deal.associated.company.name}}
{{trigger.deal.associated.line_items}}  # array para loops
{{trigger.contact.associated.deals}}    # array
```

**Associações por tipo:**
| Objeto | Associações Disponíveis |
|--------|------------------------|
| Contact | companies, deals |
| Deal | contacts, companies, line_items |
| Company | contacts, deals, tickets |
| Ticket | contacts, companies |

### 2.4 Multi-CRM (PRIORIDADE 3)

#### Interface de Normalização

```python
# app/tags/context/normalizer.py

class DataNormalizer(ABC):
    """Interface para normalizar dados de diferentes fontes"""

    @abstractmethod
    def normalize(self, data: Dict) -> Dict:
        """Normaliza dados para formato padrão"""
        pass

    @abstractmethod
    def get_associations(self, data: Dict, association_type: str) -> List[Dict]:
        """Busca objetos associados (se suportado)"""
        pass

    @abstractmethod
    def supports_associations(self) -> bool:
        """Retorna se a fonte suporta associações"""
        pass
```

#### Normalizadores a Implementar

| Normalizador | Fonte | Associações |
|--------------|-------|-------------|
| `HubSpotNormalizer` | HubSpot CRM | ✅ Sim |
| `WebhookNormalizer` | Webhook genérico | ❌ Não |
| `GoogleFormsNormalizer` | Google Forms | ❌ Não |
| `StripeNormalizer` | Stripe webhooks | ⚠️ Parcial (customer → subscriptions) |

#### Mapeamento de Conceitos (Preparação Pipedrive)

| Conceito | HubSpot | Pipedrive (futuro) | Genérico |
|----------|---------|-------------------|----------|
| Contato | Contact | Person | contact |
| Empresa | Company | Organization | company |
| Negócio | Deal | Deal | deal |
| Chamado | Ticket | - | ticket |
| Item | Line Item | Product (in deal) | line_item |

---

## 3. Arquitetura Técnica

### 3.1 Estrutura de Módulos

```
app/
  tags/                              # NOVO MÓDULO
    __init__.py                      # Exports públicos
    parser/
      __init__.py
      lexer.py                       # Tokenização
      ast.py                         # Abstract Syntax Tree
      parser.py                      # Parser principal
    transforms/
      __init__.py
      base.py                        # BaseTransform
      text.py                        # upper, lower, truncate, concat
      date.py                        # format com locale (babel)
      number.py                      # currency, round, number
    engine/
      __init__.py
      evaluator.py                   # Avalia expressões
      formula.py                     # Fórmulas matemáticas (AST seguro)
      loop.py                        # FOR loops
      conditional.py                 # IF/ELSE
      functions.py                   # SUM, ROUND, IF, AVG, etc
    context/
      __init__.py
      builder.py                     # Constrói contexto de dados
      normalizer.py                  # Interface + implementações
      global_vars.py                 # $timestamp, $date, etc
    preview/
      __init__.py
      service.py                     # TagPreviewService
```

### 3.2 Pipeline de Processamento

```
Input (texto com tags)
        ↓
┌─────────────────────────────────────┐
│ 1. LEXER                            │
│    Tokeniza: {{, }}, |, :, etc      │
└─────────────────────────────────────┘
        ↓
┌─────────────────────────────────────┐
│ 2. PARSER                           │
│    Gera AST (VariableNode,          │
│    FormulaNode, LoopNode, etc)      │
└─────────────────────────────────────┘
        ↓
┌─────────────────────────────────────┐
│ 3. CONTEXT BUILDER                  │
│    - Normaliza dados da fonte       │
│    - Injeta variáveis globais       │
│    - Resolve associações            │
└─────────────────────────────────────┘
        ↓
┌─────────────────────────────────────┐
│ 4. EVALUATOR                        │
│    - Resolve referências            │
│    - Expande loops                  │
│    - Avalia condicionais            │
│    - Aplica transforms (pipes)      │
│    - Avalia fórmulas                │
└─────────────────────────────────────┘
        ↓
Output (texto processado)
```

### 3.3 Integração com Engine Existente

**Arquivo:** `app/engine/compute_parameters.py`

```python
def compute_parameters(
    parameters,
    execution_id=None,
    trigger_output=None,
    flow_context=None,
    execution_context=None,
    previous_steps=None,
    env_vars=None,
    use_advanced_tags=True,  # NOVO FLAG
):
    context = _build_substitution_context(...)

    if use_advanced_tags:
        # Novo sistema de tags
        from app.tags import TagProcessor
        processor = TagProcessor(context)
        return processor.process(parameters)
    else:
        # Sistema legado (retrocompatibilidade)
        return _substitute_recursive(parameters, context)
```

---

## 4. Ordem de Implementação

### Fase 1: Core Parser + Transforms Básicos

**Objetivo:** Parser com sintaxe pipe + transforms de texto/data

**Arquivos:**
- `app/tags/__init__.py`
- `app/tags/parser/lexer.py`
- `app/tags/parser/ast.py`
- `app/tags/parser/parser.py`
- `app/tags/transforms/base.py`
- `app/tags/transforms/text.py`
- `app/tags/transforms/date.py`

**Testes:**
- `tests/tags/test_lexer.py`
- `tests/tags/test_parser.py`
- `tests/tags/test_transforms.py`

### Fase 2: Fórmulas + Números

**Objetivo:** Matemática segura + formatação de moeda

**Arquivos:**
- `app/tags/transforms/number.py`
- `app/tags/engine/formula.py`
- `app/tags/engine/functions.py`

**Testes:**
- `tests/tags/test_formula.py`
- `tests/tags/test_number.py`

### Fase 3: Condicionais + Loops

**Objetivo:** IF/ELSE e FOR

**Arquivos:**
- `app/tags/engine/conditional.py`
- `app/tags/engine/loop.py`
- `app/tags/engine/evaluator.py`

**Testes:**
- `tests/tags/test_conditional.py`
- `tests/tags/test_loop.py`

### Fase 4: Context Builder + Tags Globais

**Objetivo:** Normalização multi-fonte + variáveis globais

**Arquivos:**
- `app/tags/context/builder.py`
- `app/tags/context/normalizer.py` (interface + HubSpotNormalizer, WebhookNormalizer)
- `app/tags/context/global_vars.py`

**Testes:**
- `tests/tags/test_context.py`

### Fase 5: Preview API

**Objetivo:** Endpoint de preview de tags

**Arquivos:**
- `app/tags/preview/service.py`
- `app/controllers/api/v1/workflows/tags_preview.py`

**Testes:**
- `tests/tags/test_preview.py`

### Fase 6: Integração com Engine

**Objetivo:** Conectar ao pipeline existente

**Arquivos a modificar:**
- `app/engine/compute_parameters.py`
- `app/services/document_generation/tag_processor.py` (migrar/deprecar)
- `app/apps/google_docs/actions/replace_tags.py` (suporte a loops)

### Fase 7: HubSpot Expandido

**Objetivo:** Tickets, Line Items, Associações

**Arquivos:**
- `app/apps/hubspot/actions/create_ticket.py`
- `app/apps/hubspot/actions/update_ticket.py`
- `app/apps/hubspot/actions/get_ticket.py`
- `app/apps/hubspot/actions/get_line_items.py`
- `app/apps/hubspot/actions/create_line_item.py`
- `app/apps/hubspot/common/associations.py` (helper para buscar associados)
- Atualizar `app/apps/hubspot/__init__.py`

---

## 5. Arquivos Críticos

| Arquivo | Ação |
|---------|------|
| `app/engine/compute_parameters.py` | MODIFICAR - integrar novo parser |
| `app/services/document_generation/tag_processor.py` | REFERÊNCIA - lógica existente |
| `app/apps/google_docs/actions/replace_tags.py` | MODIFICAR - suporte a loops |
| `app/apps/hubspot/common/api_client.py` | REFERÊNCIA - como buscar dados |
| `app/apps/hubspot/data_source.py` | MODIFICAR - adicionar associações |
| `docg-hubspot/CLAUDE.md` | REFERÊNCIA - scopes OAuth corretos |

---

## 6. Segurança

- **Fórmulas:** Usar AST parsing seguro (NÃO `eval()`)
- **Loops:** Limite de 1000 iterações
- **Recursão:** Máximo 3 níveis de loops aninhados
- **Timeout:** 5s para processamento de tags
- **Whitelist:** Apenas funções permitidas (SUM, ROUND, IF, etc)

---

## 7. Dependências Python

```
babel>=2.12.0      # Formatação de datas com locale
```

---

## 8. Notas Importantes (do CLAUDE.md)

### OAuth Scopes HubSpot

```
# Tickets - NÃO usar crm.objects.tickets
✅ CORRETO: tickets
❌ ERRADO: crm.objects.tickets.read

# Line Items - NÃO usar crm.objects.line_items
✅ CORRETO: e-commerce
❌ ERRADO: crm.objects.line_items.read
```

### Migrations

Sempre criar migrations com Flask-Migrate:
```bash
flask db migrate -m "Add description"
flask db upgrade
```

---

## 9. Próximos Passos

1. ✅ Plano aprovado
2. ⏳ Implementar Fase 1 (Core Parser + Transforms)
3. ⏳ Implementar Fase 2 (Fórmulas)
4. ⏳ Implementar Fase 3 (Condicionais + Loops)
5. ⏳ Implementar Fase 4 (Context Builder)
6. ⏳ Implementar Fase 5 (Preview API)
7. ⏳ Implementar Fase 6 (Integração)
8. ⏳ Implementar Fase 7 (HubSpot Expandido)

---

*Documento criado em: 23 de Dezembro de 2025*
