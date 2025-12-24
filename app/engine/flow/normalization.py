"""
Normalização de nodes JSONB (React Flow) para formato do engine.

Converte a estrutura visual do workflow (nodes/edges arrays) para o formato
esperado pelo engine de execução, mantendo agnóstico em relação à fonte dos dados.
"""
from typing import List, Dict, Any


def normalize_nodes_from_jsonb(
    nodes_jsonb: List[Dict[str, Any]],
    edges_jsonb: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Converte nodes do formato React Flow para formato do engine.

    Input (React Flow format):
    {
        'id': 'node-abc123',
        'type': 'workflow',  # Tipo do componente React Flow
        'position': {'x': 100, 'y': 200},
        'data': {
            'type': 'google-docs',  # Tipo da ação
            'config': {...},        # Configuração do node
            'position': 2,          # Ordem de execução (calculado pelo frontend)
            'label': 'Generate Contract',
            'enabled': true
        }
    }

    Output (Engine format):
    {
        'id': 'node-abc123',
        'node_type': 'google-docs',
        'config': {...},
        'position': 2,
        'enabled': true,
        'structural_type': 'single',  # ou 'branch' se tem múltiplas saídas
        'branch_conditions': [...]     # Se structural_type == 'branch'
    }

    Args:
        nodes_jsonb: Array de nodes do React Flow
        edges_jsonb: Array de edges do React Flow

    Returns:
        Lista de nodes normalizados, ordenados por position
    """
    if not nodes_jsonb:
        return []

    # Build edge map para detectar branching
    edges_by_source = {}
    for edge in edges_jsonb or []:
        source = edge.get('source')
        if source:
            edges_by_source.setdefault(source, []).append(edge)

    normalized = []
    for vnode in nodes_jsonb:
        data = vnode.get('data', {})

        # Detectar branching (node tem múltiplas saídas OU edges com sourceHandle)
        outgoing_edges = edges_by_source.get(vnode['id'], [])
        has_branching = (
            len(outgoing_edges) > 1 or
            any(e.get('sourceHandle') for e in outgoing_edges)
        )

        node = {
            'id': vnode['id'],
            'node_type': data.get('type', 'unknown'),
            'config': data.get('config', {}),
            'position': data.get('position', 0),  # Frontend calculou via topological sort
            'enabled': data.get('enabled', True),
            'structural_type': 'branch' if has_branching else 'single',
        }

        # Adicionar branch_conditions se necessário
        if has_branching:
            node['branch_conditions'] = _build_branch_conditions(
                vnode['id'],
                outgoing_edges
            )

        normalized.append(node)

    # Ordenar por position (garantir ordem correta de execução)
    normalized.sort(key=lambda n: n.get('position', 999))

    return normalized


def _build_branch_conditions(
    node_id: str,
    outgoing_edges: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Constrói branch_conditions a partir de edges com sourceHandle.

    React Flow edge com condition:
    {
        'id': 'e1',
        'source': 'condition-node',
        'target': 'next-node',
        'sourceHandle': 'true',  # Conditional output
        'data': {
            'condition': {
                'field': '{{step.trigger.amount}}',
                'operator': '>',
                'value': 10000
            }
        }
    }

    Branch condition output:
    [
        {
            'name': 'True',  # Baseado no sourceHandle
            'conditions': {
                'type': 'and',
                'rules': [
                    {
                        'field': '{{step.trigger.amount}}',
                        'operator': '>',
                        'value': 10000
                    }
                ]
            },
            'next_node_id': 'next-node'
        },
        {
            'name': 'Default',
            'conditions': None,  # Default path (sem condições)
            'next_node_id': 'fallback-node'
        }
    ]

    Args:
        node_id: ID do node source
        outgoing_edges: Lista de edges saindo do node

    Returns:
        Lista de branch conditions
    """
    branches = []

    for edge in outgoing_edges:
        handle = edge.get('sourceHandle', '')
        condition_data = edge.get('data', {}).get('condition')
        target = edge.get('target')

        if not target:
            continue

        branch = {
            'name': handle.title() if handle else 'Default',
            'next_node_id': target
        }

        # Se tem condition no edge, adicionar
        if condition_data:
            branch['conditions'] = {
                'type': 'and',  # Pode ser estendido para 'or' no futuro
                'rules': [condition_data]  # Wrapped em array
            }
        else:
            # Default path (sem condições)
            branch['conditions'] = None

        branches.append(branch)

    # Ordenar: branches com conditions primeiro, default por último
    branches.sort(key=lambda b: 0 if b['conditions'] else 1)

    return branches
