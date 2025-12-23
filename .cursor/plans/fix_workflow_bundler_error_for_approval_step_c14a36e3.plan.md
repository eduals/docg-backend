---
name: ""
overview: ""
todos: []
---

# Fix workflow bundler error for approval step

## Problema Identificado

O erro ocorre porque:

1. O arquivo `lib/workflow-executor.workflow.ts` tem `"use workflow"` (linha 382)
2. Ele importa `getStepImporter` de `lib/step-registry.ts`
3. `step-registry.ts` tem import dinâmico: `() => import("@/plugins/human-in-the-loop/steps/approval")`
4. O bundler do workflow rastreia TODAS as importações transitivas quando analisa o workflow
5. `plugins/human-in-the-loop/steps/approval.ts` re-exporta de `lib/steps/approval.ts`
6. `lib/steps/approval.ts` importa `createApprovalGroup` de `lib/db/approvals.ts`
7. `lib/db/approvals.ts` usa `node:crypto` (linha 3) e importa `db` que usa `postgres` (múltiplos módulos Node.js)
8. Como `approvalStep` não tem `"use step"`, o bundler detecta módulos Node.js fora de step functions e reclama

## Análise Técnica

### Por que database-query funciona?

- `lib/steps/database-query.ts` tem `"use step"` na função `databaseQueryStep` (linha 139)
- O bundler permite módulos Node.js DENTRO de funções com `"use step"`
- Mesmo usando `postgres` (que usa vários módulos Node.js), funciona porque está dentro de `"use step"`

### Por que approval não funciona?

- `lib/steps/approval.ts` NÃO tem `"use step"` na função `approvalStep` (linha 456)
- Comentário diz: "No "use step" here - hooks are workflow-level primitives"
- Mas o bundler precisa que código que usa módulos Node.js esteja dentro de `"use step"`

### Sobre hooks e "use step"

- Hooks são definidos com `defineHook` do pacote `workflow`
- O comentário sugere que hooks não podem ser usados dentro de `"use step"`
- MAS: hooks são criados e aguardados dentro da função, não são uma diretiva de arquivo
- É possível que hooks funcionem dentro de `"use step"` - o comentário pode estar desatualizado

## Decisão: Solução Escolhida

**Opção escolhida: Adicionar "use step" na função approvalStep**

### Justificativa:

1. É a solução mais simples e direta
2. Mantém toda a lógica no mesmo lugar
3. Hooks são criados dinamicamente (`approvalHook.create()`), não são uma diretiva de arquivo
4. Se hooks realmente não funcionarem dentro de `"use step"`, descobriremos no teste e podemos ajustar

### Plano de Implementação:

1. **Adicionar "use step" na função approvalStep**

- Modificar `lib/steps/approval.ts` linha 456
- Adicionar `"use step";` como primeira linha dentro da função `approvalStep`
- Manter o comentário explicando que hooks são workflow-level primitives, mas que precisamos de "use step" para o bundler

2. **Testar se hooks funcionam dentro de "use step"**

- Executar `pnpm build` para verificar se o erro do bundler foi resolvido
- Se funcionar, problema resolvido
- Se não funcionar (hooks não funcionam dentro de "use step"), seguir para Opção 2

3. **Se Opção 1 não funcionar: Mover createApprovalGroup para API route**

- Criar API route: `app/api/workflows/approvals/create-group/route.ts`
- Mover lógica de `createApprovalGroup` para essa API route
- Modificar `lib/steps/approval.ts` para chamar a API via `fetch` ao invés de importar diretamente
- Isso isola o código que usa Node.js modules do bundle do workflow

## Arquivos a Modificar

### Opção 1 (Primeira tentativa):

- `lib/steps/approval.ts` - Adicionar `"use step";` na função `approvalStep`

### Opção 2 (Se Opção 1 falhar):

- Criar: `app/api/workflows/approvals/create-group/route.ts`
- Modificar: `lib/steps/approval.ts` - Substituir import e chamada de `createApprovalGroup` por chamada fetch
- Manter: `lib/db/approvals.ts` - Continuará sendo usado pela API route

## Testes Necessários

1. Executar `pnpm build` e verificar se o erro do bundler foi resolvido
2. Testar execução de workflow com approval step para garantir que hooks funcionam
3. Verificar se aprovações ainda funcionam corretamente (criação, email, resolução)