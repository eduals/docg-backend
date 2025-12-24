# Plano de Migração: Workflow UI Components

> **Objetivo:** Copiar componentes de sidebar/config e sistema de plugins do workflow-builder para site-docgen, integrando com docg-backend API, mantendo arquitetura extensível e corrigindo bug de nodes.

**Data:** 23 de Dezembro de 2025
**Versão:** 1.0
**Status:** 📋 Planejamento

---

## 📊 Análise Comparativa dos Projetos

### 1. **workflow-builder** (Origem - Componentes UI)

**Stack:**
- Next.js 14 + TypeScript
- @xyflow/react v12.9
- Drizzle ORM (próprio DB PostgreSQL)
- Better-auth (autenticação própria)
- Sistema de plugins modular

**Estrutura de Interesse:**

```
workflow-builder/
├── components/workflow/config/        # ⭐ COPIAR: Sidebar de configuração
│   ├── action-config.tsx             # Config principal de actions
│   ├── action-config-renderer.tsx    # Renderiza campos dinamicamente
│   ├── schema-builder.tsx            # Builder de schemas (nested fields)
│   ├── trigger-config.tsx            # Config de triggers
│   ├── condition-config.tsx          # Config de branches
│   └── fields/                       # Custom fields
│       ├── hubspot-object-type-selector.tsx
│       ├── hubspot-filter-builder.tsx
│       ├── template-selector.tsx
│       ├── signers-builder.tsx
│       └── ...
│
└── plugins/                          # ⭐ COPIAR ARQUITETURA: Sistema de plugins
    ├── _template/                    # Template base para novos plugins
    │   ├── index.ts.txt              # Definição do plugin
    │   ├── credentials.ts.txt        # Schema de credenciais
    │   ├── icon.tsx.txt              # Ícone
    │   └── steps/action.ts.txt       # Action step
    │
    ├── hubspot/                      # Exemplo real
    │   ├── index.ts                  # Plugin definition
    │   ├── credentials.ts            # OAuth config
    │   ├── icon.tsx                  # Icon component
    │   ├── services/                 # Helper services
    │   └── steps/                    # Actions (get-object, update-property)
    │
    ├── google-docs/
    ├── clicksign/
    └── registry.ts                   # Plugin registry global
```

**Características dos Plugins:**

```typescript
// Plugin Definition (index.ts)
{
  type: "hubspot",                    // Unique ID
  label: "HubSpot",                   // Display name
  description: "...",
  icon: HubSpotIcon,

  // Auth
  supportsOAuth: true,
  oAuthProvider: "hubspot",
  formFields: [...],                  // API Key fields (se não OAuth)

  // Actions
  actions: [
    {
      slug: "get-object",
      label: "Get Object",
      category: "HubSpot",
      stepFunction: "getObjectStep",
      stepImportPath: "get-object",

      // Campos de configuração dinâmicos
      configFields: [
        {
          key: "objectTypes",
          label: "Object Types",
          type: "custom",              // Tipos: text, select, custom, template-input
          customType: "hubspot-object-type-selector",
          required: true,
        },
        {
          key: "objectId",
          label: "Object ID",
          type: "template-input",      // Suporta {{NodeName.field}}
          placeholder: "{{PreviousNode.dealId}}",
          showWhen: {                  // Conditional rendering
            field: "searchMode",
            equals: "id",
          },
        },
      ],

      outputFields: [                 // Schema de output
        { field: "id", description: "Object ID" },
        { field: "properties", description: "..." },
      ],
    },
  ],
}
```

**🐛 BUG IDENTIFICADO:**
- Ao adicionar novo node, deleta nodes existentes na tela
- Problema provável: estado de nodes não está sendo preservado corretamente no `onNodesChange` ou `setNodes`

---

### 2. **site-docgen** (Destino - Atual)

**Stack:**
- Vite + React Router 7
- @xyflow/react v12.10 ✅ (JÁ TEM!)
- Radix UI ✅ (mesma lib de componentes!)
- Tailwind CSS
- Supabase (auth)

**Estrutura Atual:**

```
site-docgen/
├── app/                              # React Router 7 routes
├── components/
│   ├── ui/                           # shadcn/ui components (Radix)
│   └── workflow/                     # ⚠️ Área de trabalho
│       ├── WorkflowCanvas.tsx        # Canvas atual (básico)
│       └── ... (a expandir)
└── lib/
```

**Vantagens:**
- ✅ Já usa @xyflow/react (versão mais nova!)
- ✅ Já usa Radix UI
- ✅ Stack mais leve (Vite vs Next.js)
- ✅ Supabase já configurado

---

### 3. **project** (Referência - Funciona Corretamente)

**Stack:**
- Vite + React + TypeScript
- @xyflow/react v12.10
- Lucide icons

**Estrutura:**

```
project/src/
├── components/workflow/
│   ├── WorkflowCanvas.tsx            # ✅ REFERÊNCIA: Add nodes SEM bug
│   ├── CustomNodes.tsx               # Node components
│   ├── LeftSidebar.tsx               # Sidebar de nodes
│   └── RightSidebar.tsx              # Config sidebar
│
└── lib/
    └── flow-model.ts                 # ✅ REFERÊNCIA: State management correto
```

**🔑 SOLUÇÃO DO BUG:**

```typescript
// flow-model.ts - Gerenciamento de estado correto
export type FlowState = {
  nodes: FlowNode[];
  drop: Set<string>;
  dragging: { nodeId: NodeId } | null;
};

// WorkflowCanvas.tsx - Como adicionar nodes corretamente
const handleAddNode = useCallback((nodeData: any, clickedAddNodeId: string) => {
  setFlowState((prev) => {
    // 1. Cria novo node
    const newNode: FlowNode = {
      id: nodeData.id,
      type: nodeData.type,
      // ... data
    };

    // 2. USA flowApi para inserir SEM destruir estado anterior
    if (clickedAddNodeId === 'add-start') {
      return flowApi(prev).insertBeginning(newNode);  // ✅ Preserva prev
    }

    return flowApi(prev).insert(parentId, newNode);    // ✅ Preserva prev
  });
}, []);

// flowApi.insert() - Preserva árvore existente
insert(afterId: NodeId, newNode: FlowNode): [FlowNode, boolean] {
  // Percorre recursivamente e insere PRESERVANDO estrutura
  if (node.type === "condition") {
    for (let i = 0; i < node.then.length; i++) {
      const [updated, inserted] = nodeApi(node.then[i]).insert(afterId, newNode);
      if (inserted) {
        // Retorna NOVA árvore com node inserido
        return [{
          ...node,
          then: [
            ...node.then.slice(0, i),
            updated,
            ...node.then.slice(i + 1),
          ],
        }, true];
      }
    }
  }
}
```

**Diferença do workflow-builder:**
- ❌ workflow-builder: Usa `setNodes([...])` que SUBSTITUI array
- ✅ project: Usa `flowApi` que preserva estado imutável

---

### 4. **docg-backend** (API Backend)

**Stack:**
- Flask 3.0 + PostgreSQL
- 14 apps modulares (Automatisch-style)
- Temporal.io workflows

**Estrutura de Apps:**

```
docg-backend/app/apps/
├── base.py                           # BaseApp, ExecutionContext
├── hubspot/
│   ├── __init__.py                   # HubSpotApp class
│   ├── auth.py                       # OAuth config
│   ├── actions/                      # Actions (get-object.py, update-contact.py)
│   │   └── get_object.py             # class GetObject(BaseAction)
│   ├── triggers/                     # Triggers (new-deal.py)
│   └── common/                       # Helpers
│
├── google_docs/
│   ├── actions/
│   │   ├── copy_template.py
│   │   ├── replace_tags.py           # [v2.2] Com loops em tabelas
│   │   └── export_pdf.py
│   └── ...
│
└── clicksign/
    ├── actions/
    │   └── send_for_signature.py
    └── webhooks/
        └── signature_update.py       # [v2.2] Eventos SSE granulares
```

**Estrutura de Action (Python):**

```python
# app/apps/hubspot/actions/get_object.py

class GetObject(BaseAction):
    key = 'get-object'
    name = 'Get Object'
    description = 'Get an object from HubSpot'

    arguments = [
        ActionArgument(
            key='object_type',
            label='Object Type',
            type=ArgumentType.DROPDOWN,
            required=True,
            source=DynamicDataSource(
                handler='get_object_types'
            )
        ),
        ActionArgument(
            key='object_id',
            label='Object ID',
            type=ArgumentType.STRING,
            required=True,
            variables=True  # Aceita {{step.x.y}}
        ),
    ]

    async def run(self, $: ExecutionContext) -> ActionResult:
        object_type = $.step.parameters['object_type']
        object_id = $.step.parameters['object_id']

        # Busca no HubSpot via $.http (já autenticado)
        response = await $.http.get(f'/crm/v3/objects/{object_type}/{object_id}')

        return ActionResult(
            raw=response.json(),
            data={
                'id': response.json()['id'],
                'properties': response.json()['properties'],
            }
        )
```

---

## 🎯 Estratégia de Migração

### Princípios

1. **Copiar UI, não lógica de backend** - workflow-builder tem próprio DB, vamos usar API Flask
2. **Manter arquitetura de plugins** - Estrutura de pastas compatível para futuro sync backend
3. **Corrigir bug de nodes** - Usar `flow-model.ts` do projeto original
4. **Design system consistente** - Aproveitar que ambos usam Radix UI

---

## 📋 Plano de Execução

### **Fase 1: Setup Base e Correção do Bug** 🔴 CRÍTICO

#### 1.1 Copiar Flow Model Correto

**Origem:** `/Users/eduardoalmeida/Downloads/project/src/lib/flow-model.ts`
**Destino:** `site-docgen/app/lib/workflow/flow-model.ts`

**Ações:**
- Copiar `flow-model.ts` completo (FlowState, nodeApi, flowApi)
- Copiar `flow-layout.ts` (buildReactFlow)
- Adaptar tipos para incluir tipos de nodes do PipeHub:
  - `trigger` (HubSpot, Forms, Webhook)
  - `action` (Google Docs, ClickSign, Email)
  - `branch` (Conditional paths)
  - `approval` (Human-in-the-loop)

**Novos tipos:**

```typescript
// site-docgen/app/lib/workflow/flow-model.ts

export type TriggerNode = {
  type: "trigger";
  id: NodeId;
  appType: string;           // "hubspot", "google-forms"
  triggerKey: string;        // "new-deal", "new-response"
  config: Record<string, unknown>;
  drop: Set<string>;
  dragging: DragPos;
};

export type ActionNode = {
  type: "action";
  id: NodeId;
  appType: string;           // "google-docs", "clicksign"
  actionKey: string;         // "copy-template", "send-for-signature"
  config: Record<string, unknown>;
  drop: Set<string>;
  dragging: DragPos;
};

export type BranchNode = {
  type: "branch";
  id: NodeId;
  conditions: BranchCondition[];
  branches: {
    [branchId: string]: FlowNode[];
  };
  drop: Set<string>;
  dragging: DragPos;
};

export type ApprovalNode = {
  type: "approval";
  id: NodeId;
  approvers: string[];       // User emails
  timeout: number;           // Minutes
  drop: Set<string>;
  dragging: DragPos;
};

export type FlowNode = TriggerNode | ActionNode | BranchNode | ApprovalNode;
```

#### 1.2 Copiar WorkflowCanvas Correto

**Origem:** `project/src/components/workflow/WorkflowCanvas.tsx`
**Destino:** `site-docgen/app/components/workflow/WorkflowCanvas.tsx`

**Adaptações:**
- Usar `nodeTypes` do PipeHub (trigger, action, branch, approval)
- Manter lógica de `handleAddNode` (SEM bug)
- Integrar com API Flask:
  - `GET /api/v1/workflows/{id}` - Load workflow
  - `PUT /api/v1/workflows/{id}` - Save workflow

#### 1.3 Criar Custom Nodes do PipeHub

**Destino:** `site-docgen/app/components/workflow/nodes/`

Criar nodes visuais:
- `TriggerNode.tsx` - Node de trigger (ícone do app + nome)
- `ActionNode.tsx` - Node de action
- `BranchNode.tsx` - Node de branch (paths condicionais)
- `ApprovalNode.tsx` - Node de aprovação
- `AddNode.tsx` - Botão "+" para adicionar nodes

**Design:**
- Seguir design do workflow-builder (mais bonito)
- Ícones dinâmicos baseados em `appType`
- Badge de status (pending, running, success, failed)

---

### **Fase 2: Sistema de Plugins (Arquitetura Frontend)** 🟡

#### 2.1 Criar Registry de Plugins

**Destino:** `site-docgen/app/lib/plugins/registry.ts`

```typescript
// site-docgen/app/lib/plugins/registry.ts

export type PluginFieldType =
  | "text"
  | "template-input"        // Suporta {{NodeName.field}}
  | "template-textarea"
  | "select"
  | "custom";               // Custom component

export type PluginConfigField = {
  key: string;
  label: string;
  type: PluginFieldType;
  customType?: string;      // Se type === "custom"
  placeholder?: string;
  required?: boolean;
  options?: { value: string; label: string }[];
  showWhen?: {              // Conditional rendering
    field: string;
    equals: string;
  };
};

export type PluginAction = {
  slug: string;
  label: string;
  description: string;
  category: string;
  configFields: PluginConfigField[];
  outputFields?: { field: string; description: string }[];
};

export type IntegrationPlugin = {
  type: string;             // "hubspot", "google-docs"
  label: string;
  description: string;
  icon: React.ComponentType;

  // Auth
  supportsOAuth?: boolean;
  oAuthProvider?: string;

  // Actions/Triggers
  actions: PluginAction[];
  triggers?: PluginAction[];
};

// Global registry
const plugins = new Map<string, IntegrationPlugin>();

export function registerPlugin(plugin: IntegrationPlugin) {
  plugins.set(plugin.type, plugin);
}

export function getPlugin(type: string): IntegrationPlugin | undefined {
  return plugins.get(type);
}

export function getAllPlugins(): IntegrationPlugin[] {
  return Array.from(plugins.values());
}

export function getAction(appType: string, actionSlug: string): PluginAction | undefined {
  const plugin = getPlugin(appType);
  return plugin?.actions.find(a => a.slug === actionSlug);
}
```

#### 2.2 Criar Estrutura de Plugins

**Destino:** `site-docgen/app/lib/plugins/`

```
site-docgen/app/lib/plugins/
├── registry.ts                       # Plugin registry
├── _template/                        # Template para novos plugins
│   └── README.md                     # Instruções
│
├── hubspot/
│   ├── index.ts                      # Plugin definition
│   ├── icon.tsx                      # HubSpot icon
│   └── fields/                       # Custom fields
│       ├── ObjectTypeSelector.tsx    # Dropdown de object types
│       └── PropertySelector.tsx      # Dropdown de properties
│
├── google-docs/
│   ├── index.ts
│   ├── icon.tsx
│   └── fields/
│       └── TemplateSelector.tsx      # Dropdown de templates
│
├── clicksign/
│   ├── index.ts
│   ├── icon.tsx
│   └── fields/
│       └── SignersBuilder.tsx        # Lista de signatários
│
└── index.ts                          # Auto-import all plugins
```

#### 2.3 Implementar Plugins (Frontend Only)

**Exemplo: HubSpot Plugin**

```typescript
// site-docgen/app/lib/plugins/hubspot/index.ts

import { registerPlugin } from '../registry';
import { HubSpotIcon } from './icon';

registerPlugin({
  type: 'hubspot',
  label: 'HubSpot',
  description: 'Access HubSpot CRM data',
  icon: HubSpotIcon,

  supportsOAuth: true,
  oAuthProvider: 'hubspot',

  actions: [
    {
      slug: 'get-object',
      label: 'Get Object',
      description: 'Get an object (deal, contact, company) from HubSpot',
      category: 'HubSpot',

      configFields: [
        {
          key: 'object_type',
          label: 'Object Type',
          type: 'custom',
          customType: 'hubspot-object-type-selector',
          required: true,
        },
        {
          key: 'search_mode',
          label: 'Search Mode',
          type: 'select',
          options: [
            { value: 'id', label: 'By Object ID' },
            { value: 'filter', label: 'By Filter' },
          ],
          required: true,
        },
        {
          key: 'object_id',
          label: 'Object ID',
          type: 'template-input',
          placeholder: '{{PreviousNode.dealId}}',
          required: true,
          showWhen: { field: 'search_mode', equals: 'id' },
        },
      ],

      outputFields: [
        { field: 'id', description: 'Object ID' },
        { field: 'properties', description: 'Object properties' },
      ],
    },

    {
      slug: 'update-property',
      label: 'Update Property',
      description: 'Update a property of a HubSpot object',
      category: 'HubSpot',

      configFields: [
        {
          key: 'object_type',
          label: 'Object Type',
          type: 'custom',
          customType: 'hubspot-object-type-selector',
          required: true,
        },
        {
          key: 'object_id',
          label: 'Object ID',
          type: 'template-input',
          placeholder: '{{PreviousNode.id}}',
          required: true,
        },
        {
          key: 'property',
          label: 'Property to Update',
          type: 'custom',
          customType: 'hubspot-property-selector',
          required: true,
        },
        {
          key: 'property_value',
          label: 'Property Value',
          type: 'template-input',
          placeholder: 'New value or {{PreviousNode.email}}',
          required: true,
        },
      ],
    },
  ],
});
```

**Plugins a Implementar:**

1. **hubspot** - Get object, Update property, Create contact, Create deal
2. **google-docs** - Copy template, Replace tags, Export PDF
3. **google-slides** - Copy template, Replace tags, Export PDF
4. **google-drive** - Upload file, Download file
5. **clicksign** - Send for signature
6. **zapsign** - Send for signature
7. **gmail** - Send email
8. **outlook** - Send email
9. **ai** - Generate text (OpenAI)
10. **stripe** - Create checkout

---

### **Fase 3: Config Sidebar (Componentes Dinâmicos)** 🟢

#### 3.1 Copiar Componentes Base

**Origem:** `workflow-builder/components/workflow/config/`
**Destino:** `site-docgen/app/components/workflow/config/`

Copiar:
- ✅ `action-config-renderer.tsx` - **CORE:** Renderiza campos dinamicamente
- ✅ `schema-builder.tsx` - Builder de schemas (arrays, objects)
- ✅ `custom-field-renderer.tsx` - Renderiza custom fields

**Adaptações:**
- Trocar imports de `@/lib/integrations-store` por `@/lib/plugins/registry`
- Remover dependência de Jotai (usar React Context)
- Remover lógica de DB (Drizzle) - usar API calls

#### 3.2 Copiar Custom Fields

**Origem:** `workflow-builder/components/workflow/config/fields/`
**Destino:** `site-docgen/app/components/workflow/config/fields/`

Copiar e adaptar:
- ✅ `hubspot-object-type-selector.tsx` - Dropdown de object types
- ✅ `hubspot-property-selector.tsx` - Dropdown de properties (dinâmico)
- ✅ `hubspot-filter-builder.tsx` - Builder de filtros HubSpot
- ✅ `template-selector.tsx` - Dropdown de templates do Drive
- ✅ `signers-builder.tsx` - Lista de signatários (email + role)
- ✅ `approvers-builder.tsx` - Lista de aprovadores
- ✅ `folder-selector.tsx` - Selector de pasta do Drive

**Integração com API:**

```typescript
// Exemplo: template-selector.tsx

export function TemplateSelector({ value, onChange }: Props) {
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Buscar templates da API Flask
    fetch('/api/v1/templates', {
      headers: {
        'Authorization': `Bearer ${token}`,
        'X-Organization-ID': orgId,
      },
    })
      .then(res => res.json())
      .then(data => {
        setTemplates(data.templates);
        setLoading(false);
      });
  }, []);

  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger>
        <SelectValue placeholder={loading ? "Loading..." : "Select template"} />
      </SelectTrigger>
      <SelectContent>
        {templates.map(t => (
          <SelectItem key={t.id} value={t.id}>
            {t.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
```

#### 3.3 Criar RightSidebar Principal

**Destino:** `site-docgen/app/components/workflow/RightSidebar.tsx`

**Funcionalidades:**
- Mostrar config do node selecionado
- Renderizar campos dinamicamente via `action-config-renderer`
- Salvar mudanças no workflow state
- Preview de variáveis `{{NodeName.field}}`

```typescript
// RightSidebar.tsx (estrutura)

export function RightSidebar({
  selectedNode,
  onUpdateNode
}: Props) {
  if (!selectedNode) {
    return <EmptyState />;
  }

  // Buscar plugin definition
  const plugin = getPlugin(selectedNode.appType);
  const action = getAction(selectedNode.appType, selectedNode.actionKey);

  if (!action) return null;

  return (
    <div className="w-96 border-l bg-background">
      <div className="p-4 border-b">
        <div className="flex items-center gap-2">
          <plugin.icon className="w-5 h-5" />
          <h3>{action.label}</h3>
        </div>
        <p className="text-sm text-muted-foreground">{action.description}</p>
      </div>

      <div className="p-4 space-y-4">
        <ActionConfigRenderer
          configFields={action.configFields}
          config={selectedNode.config}
          onUpdateConfig={(key, value) => {
            onUpdateNode({
              ...selectedNode,
              config: { ...selectedNode.config, [key]: value },
            });
          }}
        />
      </div>
    </div>
  );
}
```

---

### **Fase 4: Integração com API Flask** 🔵

#### 4.1 Criar API Client

**Destino:** `site-docgen/app/lib/api/workflows.ts`

```typescript
// API Client para workflows

export async function getWorkflow(workflowId: string) {
  const response = await fetch(`/api/v1/workflows/${workflowId}`, {
    headers: {
      'Authorization': `Bearer ${getToken()}`,
      'X-Organization-ID': getOrgId(),
    },
  });

  return response.json();
}

export async function saveWorkflow(workflowId: string, data: any) {
  const response = await fetch(`/api/v1/workflows/${workflowId}`, {
    method: 'PUT',
    headers: {
      'Authorization': `Bearer ${getToken()}`,
      'X-Organization-ID': getOrgId(),
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });

  return response.json();
}

export async function executeWorkflow(workflowId: string, triggerData?: any) {
  const response = await fetch(`/api/v1/workflows/${workflowId}/executions`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${getToken()}`,
      'X-Organization-ID': getOrgId(),
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ trigger_data: triggerData }),
  });

  return response.json();
}
```

#### 4.2 Mapear Plugins Frontend → Apps Backend

**Conversão:**

Frontend (UI):
```typescript
{
  type: "action",
  appType: "google-docs",
  actionKey: "copy-template",
  config: {
    template_id: "{{env.TEMPLATE_ID}}",
    folder_id: "abc123",
  }
}
```

Backend (API - WorkflowNode):
```json
{
  "id": "node-123",
  "type": "action",
  "parameters": {
    "app_key": "google-docs",
    "action_key": "copy-template",
    "template_id": "{{env.TEMPLATE_ID}}",
    "folder_id": "abc123"
  }
}
```

**Adapter:**

```typescript
// site-docgen/app/lib/adapters/workflow-adapter.ts

export function frontendToBackend(flowState: FlowState): BackendWorkflow {
  // Converte FlowNode[] para WorkflowNode[] do backend

  function convertNode(node: FlowNode): BackendWorkflowNode {
    if (node.type === 'action') {
      return {
        id: node.id,
        type: 'action',
        parameters: {
          app_key: node.appType,
          action_key: node.actionKey,
          ...node.config,
        },
      };
    }

    if (node.type === 'branch') {
      return {
        id: node.id,
        type: 'action',
        structural_type: 'branch',
        branch_conditions: convertBranchConditions(node.conditions),
        parameters: {},
      };
    }

    // ... outros tipos
  }

  return {
    nodes: flowState.nodes.map(convertNode),
  };
}

export function backendToFrontend(workflow: BackendWorkflow): FlowState {
  // Converte WorkflowNode[] para FlowNode[]
  // ...
}
```

#### 4.3 Dynamic Data (Dropdowns)

Alguns campos precisam buscar dados da API:

**Exemplo: Object Types do HubSpot**

```typescript
// site-docgen/app/lib/plugins/hubspot/fields/ObjectTypeSelector.tsx

export function ObjectTypeSelector({ value, onChange }: Props) {
  const [objectTypes, setObjectTypes] = useState([]);

  useEffect(() => {
    // Buscar object types via API
    fetch('/api/v1/apps/hubspot/dynamic-data/object-types', {
      headers: { 'Authorization': `Bearer ${token}` },
    })
      .then(res => res.json())
      .then(data => setObjectTypes(data.options));
  }, []);

  return (
    <Select value={value} onValueChange={onChange}>
      {objectTypes.map(opt => (
        <SelectItem key={opt.value} value={opt.value}>
          {opt.label}
        </SelectItem>
      ))}
    </Select>
  );
}
```

**Endpoints Necessários no Backend:**

```python
# app/apps/hubspot/dynamic_data.py (NOVO)

@bp.route('/apps/hubspot/dynamic-data/object-types', methods=['GET'])
@require_auth
def get_object_types():
    return jsonify({
        'options': [
            {'value': 'deals', 'label': 'Deals'},
            {'value': 'contacts', 'label': 'Contacts'},
            {'value': 'companies', 'label': 'Companies'},
            {'value': 'tickets', 'label': 'Tickets'},
        ]
    })

@bp.route('/apps/hubspot/dynamic-data/properties', methods=['GET'])
@require_auth
def get_properties():
    object_type = request.args.get('object_type')

    # Buscar properties do HubSpot API
    # ...

    return jsonify({
        'options': [
            {'value': 'dealname', 'label': 'Deal Name'},
            {'value': 'amount', 'label': 'Amount'},
            # ...
        ]
    })
```

---

### **Fase 5: LeftSidebar (Node Picker)** 🟣

#### 5.1 Criar LeftSidebar

**Destino:** `site-docgen/app/components/workflow/LeftSidebar.tsx`

**Funcionalidades:**
- Lista de apps agrupados por categoria
- Search/filter
- Drag & drop ou click para adicionar node

```typescript
export function LeftSidebar({ onAddNode }: Props) {
  const plugins = getAllPlugins();
  const [search, setSearch] = useState('');

  const categories = useMemo(() => {
    const cats = new Map<string, IntegrationPlugin[]>();

    plugins.forEach(plugin => {
      plugin.actions.forEach(action => {
        if (!cats.has(action.category)) {
          cats.set(action.category, []);
        }
        cats.get(action.category)!.push(plugin);
      });
    });

    return cats;
  }, [plugins]);

  return (
    <div className="w-64 border-r bg-background">
      <div className="p-4 border-b">
        <Input
          placeholder="Search actions..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      <div className="p-2 space-y-2">
        {Array.from(categories.entries()).map(([category, plugins]) => (
          <Collapsible key={category}>
            <CollapsibleTrigger>{category}</CollapsibleTrigger>
            <CollapsibleContent>
              {plugins.map(plugin => (
                <div
                  key={plugin.type}
                  className="flex items-center gap-2 p-2 hover:bg-accent cursor-pointer rounded"
                  onClick={() => onAddNode({
                    type: 'action',
                    appType: plugin.type,
                    actionKey: 'default',  // ou mostrar submenu
                  })}
                >
                  <plugin.icon className="w-4 h-4" />
                  <span className="text-sm">{plugin.label}</span>
                </div>
              ))}
            </CollapsibleContent>
          </Collapsible>
        ))}
      </div>
    </div>
  );
}
```

---

### **Fase 6: Testes e Refinamento** ⚪

#### 6.1 Testar Fluxo Completo

1. **Criar workflow:**
   - Adicionar trigger (HubSpot "new-deal")
   - Adicionar action (Google Docs "copy-template")
   - Configurar campos
   - Salvar

2. **Executar workflow:**
   - Trigger manual
   - Verificar SSE events
   - Ver logs estruturados
   - Verificar documento gerado

3. **Editar workflow:**
   - Adicionar branch
   - Adicionar approval
   - Adicionar signature
   - Salvar mudanças

#### 6.2 Validações

- ✅ Nodes não são deletados ao adicionar novos
- ✅ Config é preservada ao editar
- ✅ Variáveis `{{NodeName.field}}` funcionam
- ✅ Custom fields carregam dados da API
- ✅ Workflow salva/carrega corretamente

---

## 📁 Estrutura Final do site-docgen

```
site-docgen/
├── app/
│   ├── routes/
│   │   └── workflows.$id.tsx              # Página de edição de workflow
│   │
│   ├── components/
│   │   ├── ui/                            # shadcn/ui (já existe)
│   │   │
│   │   └── workflow/
│   │       ├── WorkflowCanvas.tsx         # ✅ Canvas com nodes (SEM bug)
│   │       ├── LeftSidebar.tsx            # ✅ Node picker
│   │       ├── RightSidebar.tsx           # ✅ Config sidebar
│   │       │
│   │       ├── nodes/                     # Custom nodes
│   │       │   ├── TriggerNode.tsx
│   │       │   ├── ActionNode.tsx
│   │       │   ├── BranchNode.tsx
│   │       │   ├── ApprovalNode.tsx
│   │       │   └── AddNode.tsx
│   │       │
│   │       └── config/                    # Config components
│   │           ├── ActionConfigRenderer.tsx
│   │           ├── SchemaBuilder.tsx
│   │           ├── CustomFieldRenderer.tsx
│   │           │
│   │           └── fields/                # Custom fields
│   │               ├── HubSpotObjectTypeSelector.tsx
│   │               ├── HubSpotPropertySelector.tsx
│   │               ├── TemplateSelector.tsx
│   │               ├── SignersBuilder.tsx
│   │               └── ApproversBuilder.tsx
│   │
│   └── lib/
│       ├── workflow/
│       │   ├── flow-model.ts              # ✅ State management (SEM bug)
│       │   └── flow-layout.ts             # Layout algorithm
│       │
│       ├── plugins/
│       │   ├── registry.ts                # Plugin registry
│       │   ├── _template/                 # Template para novos
│       │   ├── hubspot/
│       │   │   ├── index.ts               # Plugin definition
│       │   │   ├── icon.tsx
│       │   │   └── fields/
│       │   ├── google-docs/
│       │   ├── clicksign/
│       │   ├── gmail/
│       │   └── index.ts                   # Auto-import all
│       │
│       ├── api/
│       │   └── workflows.ts               # API client
│       │
│       └── adapters/
│           └── workflow-adapter.ts        # Frontend ↔ Backend conversion
│
└── package.json
```

---

## 🔄 Mapeamento Plugin Frontend → App Backend

| Frontend Plugin | Backend App | Actions |
|-----------------|-------------|---------|
| `hubspot` | `app/apps/hubspot` | get-object, update-property, create-contact, create-deal |
| `google-docs` | `app/apps/google_docs` | copy-template, replace-tags, export-pdf |
| `google-slides` | `app/apps/google_slides` | copy-template, replace-tags, export-pdf |
| `google-drive` | `app/apps/google_drive` | upload-file, download-file |
| `gmail` | `app/apps/gmail` | send-email |
| `outlook` | `app/apps/outlook` | send-email |
| `clicksign` | `app/apps/clicksign` | send-for-signature |
| `zapsign` | `app/apps/zapsign` | create-document |
| `ai` | `app/apps/ai` | generate-text |
| `stripe` | `app/apps/stripe` | create-checkout |

---

## 🐛 Correção do Bug de Nodes

### Problema

**workflow-builder:**
```typescript
// ❌ ERRADO: Substitui array inteiro
const addNode = () => {
  setNodes([newNode]);  // Deleta todos os outros!
};
```

### Solução

**project (correto):**
```typescript
// ✅ CORRETO: Usa estado imutável
const handleAddNode = useCallback((nodeData, addNodeId) => {
  setFlowState((prev) => {
    const newNode = { id: nodeData.id, type: nodeData.type, ... };

    // flowApi preserva árvore existente
    return flowApi(prev).insert(parentId, newNode);
  });
}, []);

// flowApi.insert() - Imutável
insert(afterId, newNode): [FlowNode, boolean] {
  if (node.type === "condition") {
    for (let i = 0; i < node.then.length; i++) {
      const [updated, inserted] = nodeApi(node.then[i]).insert(afterId, newNode);

      if (inserted) {
        // Retorna NOVA árvore preservando estrutura
        return [{
          ...node,
          then: [
            ...node.then.slice(0, i),   // Antes
            updated,                     // Node atualizado
            ...node.then.slice(i + 1),  // Depois
          ],
        }, true];
      }
    }
  }
}
```

**Implementar em site-docgen:**
- ✅ Copiar `flow-model.ts` do projeto original
- ✅ Adaptar tipos para nodes do PipeHub
- ✅ Usar `flowApi` em vez de `setNodes([...])`

---

## 📝 Checklist de Implementação

### Fase 1: Setup Base ✅
- [ ] Copiar `flow-model.ts` do projeto original
- [ ] Adaptar tipos (TriggerNode, ActionNode, BranchNode, ApprovalNode)
- [ ] Copiar `WorkflowCanvas.tsx` (preservar lógica de addNode)
- [ ] Criar custom nodes (TriggerNode, ActionNode, etc.)
- [ ] Testar: Adicionar 5 nodes → Verificar que nenhum é deletado

### Fase 2: Sistema de Plugins ✅
- [ ] Criar `registry.ts`
- [ ] Criar estrutura de pastas `lib/plugins/`
- [ ] Implementar plugin HubSpot
- [ ] Implementar plugin Google Docs
- [ ] Implementar plugin ClickSign
- [ ] Implementar plugin Gmail
- [ ] Auto-import em `lib/plugins/index.ts`

### Fase 3: Config Sidebar ✅
- [ ] Copiar `ActionConfigRenderer.tsx`
- [ ] Copiar `SchemaBuilder.tsx`
- [ ] Copiar custom fields:
  - [ ] HubSpotObjectTypeSelector
  - [ ] HubSpotPropertySelector
  - [ ] TemplateSelector
  - [ ] SignersBuilder
  - [ ] ApproversBuilder
- [ ] Criar `RightSidebar.tsx`
- [ ] Integrar com workflow state

### Fase 4: Integração com API ✅
- [ ] Criar API client (`lib/api/workflows.ts`)
- [ ] Criar adapter frontend ↔ backend
- [ ] Implementar endpoints de dynamic data no backend:
  - [ ] `/apps/hubspot/dynamic-data/object-types`
  - [ ] `/apps/hubspot/dynamic-data/properties`
  - [ ] `/apps/google-docs/dynamic-data/templates`
- [ ] Testar save/load workflow

### Fase 5: LeftSidebar ✅
- [ ] Criar `LeftSidebar.tsx`
- [ ] Agrupar por categoria
- [ ] Implementar search
- [ ] Implementar add node (click ou drag)

### Fase 6: Testes ✅
- [ ] Criar workflow completo (trigger → action → branch → approval → signature)
- [ ] Executar workflow e verificar SSE
- [ ] Editar workflow e verificar que mudanças são salvas
- [ ] Verificar variáveis `{{NodeName.field}}` funcionam
- [ ] Testar com 10+ nodes (sem deletar)

---

## 🎨 Design System

**Componentes a Reaproveitar:**
- ✅ Radix UI (ambos já usam)
- ✅ Tailwind CSS
- ✅ shadcn/ui components
- ✅ Lucide icons

**Estilos do workflow-builder a Copiar:**
- Node design (rounded, shadow, badges)
- Sidebar layout (sticky, scrollable)
- Config fields (labels, placeholders, help text)

---

## 🚀 Ordem de Implementação Recomendada

1. **Semana 1: Base + Bug Fix**
   - Copiar flow-model.ts
   - Copiar WorkflowCanvas.tsx
   - Criar custom nodes
   - TESTAR: Adicionar 10 nodes sem deletar ✅

2. **Semana 2: Plugins**
   - Criar registry
   - Implementar 3 plugins principais (HubSpot, Google Docs, ClickSign)
   - TESTAR: Plugins registrados corretamente ✅

3. **Semana 3: Config Sidebar**
   - Copiar config components
   - Copiar custom fields
   - Criar RightSidebar
   - TESTAR: Config funciona e salva ✅

4. **Semana 4: Integração API**
   - API client
   - Adapter
   - Dynamic data endpoints
   - TESTAR: Save/load workflow da API ✅

5. **Semana 5: LeftSidebar + Polish**
   - LeftSidebar
   - Refinamento visual
   - Testes end-to-end ✅

---

## 📚 Documentação Futura

Após implementação, criar:
- `PLUGINS.md` - Como criar novos plugins frontend
- `WORKFLOW_UI.md` - Arquitetura da UI de workflows
- `CUSTOM_FIELDS.md` - Como criar custom fields

---

**Status:** 📋 Plano Pronto - Aguardando Aprovação para Execução
