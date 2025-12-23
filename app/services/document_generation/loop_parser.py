"""
Loop Parser - Parsing de loops para duplicação de linhas de tabela.

Feature 3: Loops em Google Docs
Sintaxe: {{FOR item IN array}}...{{END FOR}}
"""

import re
from typing import List, Dict, Any


def parse_loops(content: str) -> List[Dict[str, Any]]:
    """
    Detecta loops no formato {{FOR item IN array}}...{{END FOR}}

    Args:
        content: Texto a ser analisado

    Returns:
        Lista de loops encontrados:
        [
            {
                'start': 120,  # Índice de início
                'end': 350,    # Índice de fim
                'var_name': 'item',
                'array_path': 'step.abc.line_items',
                'content': '{{item.name}} - {{item.price}}'
            }
        ]

    Examples:
        >>> parse_loops("{{FOR item IN line_items}}{{item.name}}{{END FOR}}")
        [{'start': 0, 'end': 52, 'var_name': 'item', 'array_path': 'line_items', 'content': '{{item.name}}'}]
    """
    loops = []
    pattern = r'\{\{FOR\s+(\w+)\s+IN\s+([\w\.]+)\}\}(.*?)\{\{END\s+FOR\}\}'

    for match in re.finditer(pattern, content, re.DOTALL | re.IGNORECASE):
        loops.append({
            'start': match.start(),
            'end': match.end(),
            'var_name': match.group(1),  # 'item'
            'array_path': match.group(2),  # 'step.abc.line_items' ou 'line_items'
            'content': match.group(3),  # conteúdo dentro do loop
        })

    return loops


def resolve_array(array_path: str, context: Dict) -> List[Any]:
    """
    Resolve path de array para valores.

    Args:
        array_path: Path do array (ex: 'step.abc.line_items' ou 'line_items')
        context: Dicionário de contexto com variáveis disponíveis

    Returns:
        Lista de valores ou lista vazia se não encontrado

    Examples:
        >>> context = {'line_items': [{'name': 'A'}, {'name': 'B'}]}
        >>> resolve_array('line_items', context)
        [{'name': 'A'}, {'name': 'B'}]

        >>> context = {'step': {'abc': {'line_items': [1, 2, 3]}}}
        >>> resolve_array('step.abc.line_items', context)
        [1, 2, 3]
    """
    parts = array_path.split('.')
    value = context

    for part in parts:
        if isinstance(value, dict):
            value = value.get(part)
        else:
            return []

        if value is None:
            return []

    # Garantir que é lista
    if not isinstance(value, list):
        return []

    return value


def extract_item_fields(content: str, var_name: str) -> List[str]:
    """
    Extrai campos referenciados de um item dentro do loop.

    Args:
        content: Conteúdo do loop
        var_name: Nome da variável do item (ex: 'item')

    Returns:
        Lista de campos (ex: ['name', 'price', 'quantity'])

    Examples:
        >>> extract_item_fields('{{item.name}} - {{item.price}}', 'item')
        ['name', 'price']
    """
    pattern = rf'\{{\{{{var_name}\.(\w+)\}}\}}'
    matches = re.findall(pattern, content)
    # Remover duplicatas mantendo ordem
    seen = set()
    fields = []
    for field in matches:
        if field not in seen:
            seen.add(field)
            fields.append(field)
    return fields
