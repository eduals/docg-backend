---
name: Corrigir traduções na tabela de comparação
overview: O problema é que as chaves de tradução estão com o caminho incorreto. No JSON, `comparison` está aninhado dentro de `pricing`, mas o código está chamando `t('comparison.*')` ao invés de `t('pricing.comparison.*')`.
todos:
  - id: fix-comparison-keys
    content: Substituir todas as chamadas t('comparison.*') por t('pricing.comparison.*') no Pricing.tsx
    status: completed
---

# Corrigir Caminho das Chaves de Tradução

## Problema Identificado

No arquivo `landing.json`, a estrutura é:

```json
{
  "pricing": {
    "comparison": {
      "title": "Comparação Completa de Planos",
      ...
    }
  }
}
```

No componente `Pricing.tsx`, as chamadas estão incorretas:

- Atual: `t('comparison.title')`
- Correto: `t('pricing.comparison.title')`

## Solução

Atualizar todas as chamadas `t('comparison.*')` para `t('pricing.comparison.*')` no arquivo `/Users/user/Documents/CODE/docugen-hs/website/site-docgen/src/components/Pricing.tsx`.

### Substituições Necessárias

| De | Para |

|---|---|

| `t('comparison.features.*')` | `t('pricing.comparison.features.*')` |

| `t('comparison.values.*')` | `t('pricing.comparison.values.*')` |

| `t('comparison.plans.*')` | `t('pricing.comparison.plans.*')` |

| `t('comparison.categories.*')` | `t('pricing.comparison.categories.*')` |

| `t('comparison.title')` | `t('pricing.comparison.title')` |

| `t('comparison.hideComparison')` | `t('pricing.comparison.hideComparison')` |

| `t('comparison.viewComparison')` | `t('pricing.comparison.viewComparison')` |

### Arquivo a Modificar

`/Users/user/Documents/CODE/docugen-hs/website/site-docgen/src/components/Pricing.tsx`

- Linhas 56-189: useMemo com comparisonData
- Linhas 197, 199: renderComparisonValue
- Linhas 275, 286, 294-299, 306, 322, 338, 354: JSX da tabela