"""
Table Loops - Detecta e processa loops dentro de tabelas do Google Docs.

Feature 3: Loops em Google Docs
Duplica linhas de tabela para arrays de objetos.
"""

import re
from typing import List, Dict, Any
from app.services.document_generation.loop_parser import parse_loops, extract_item_fields


def detect_table_loops(document: Dict[str, Any]) -> List[Dict]:
    """
    Detecta loops dentro de linhas de tabela.

    Args:
        document: Documento do Google Docs (resultado de documents().get())

    Returns:
        Lista de loops encontrados em tabelas:
        [
            {
                'table_start_index': 1234,
                'table_index': 0,
                'row_index': 2,
                'loops': [...],  # resultado de parse_loops()
                'row_text': '{{FOR item IN line_items}}...'
            }
        ]
    """
    table_loops = []

    for element in document.get('body', {}).get('content', []):
        if 'table' not in element:
            continue

        table = element['table']
        table_start = element['startIndex']

        for row_idx, row in enumerate(table.get('tableRows', [])):
            # Concatenar texto de todas as células da linha
            row_text = ''
            for cell in row.get('tableCells', []):
                for content in cell.get('content', []):
                    if 'paragraph' in content:
                        for elem in content['paragraph'].get('elements', []):
                            if 'textRun' in elem:
                                row_text += elem['textRun'].get('content', '')

            # Verificar se tem loop
            loops = parse_loops(row_text)
            if loops:
                table_loops.append({
                    'table_start_index': table_start,
                    'table_index': len(table_loops),
                    'row_index': row_idx,
                    'loops': loops,
                    'row_text': row_text,
                })

    return table_loops


def build_duplicate_row_requests(
    table_loop: Dict,
    array_data: List[Dict],
) -> List[Dict]:
    """
    Gera requests do Google Docs API para duplicar linha.

    Para cada item no array, duplica a linha e substitui {{item.field}}.

    Args:
        table_loop: Informações do loop da tabela (de detect_table_loops)
        array_data: Array de objetos a iterar

    Returns:
        Lista de requests para Google Docs batchUpdate API

    Examples:
        >>> table_loop = {
        ...     'table_start_index': 100,
        ...     'row_index': 1,
        ...     'loops': [{'var_name': 'item', 'content': '{{item.name}} - {{item.price}}'}]
        ... }
        >>> array_data = [{'name': 'Product A', 'price': 100}, {'name': 'Product B', 'price': 200}]
        >>> requests = build_duplicate_row_requests(table_loop, array_data)
        >>> len([r for r in requests if 'insertTableRow' in r])  # Deve inserir 1 linha (N-1)
        1
    """
    if not array_data:
        return []

    requests = []

    # 1. Inserir novas linhas (N-1 cópias, pois já existe 1 linha original)
    for i in range(len(array_data) - 1):
        requests.append({
            'insertTableRow': {
                'tableCellLocation': {
                    'tableStartLocation': {'index': table_loop['table_start_index']},
                    'rowIndex': table_loop['row_index'] + i + 1,
                },
                'insertBelow': True,
            }
        })

    # 2. Para cada linha, substituir {{item.field}} pelos valores do array
    for idx, item_data in enumerate(array_data):
        # Substituir tags dentro da linha
        for loop in table_loop['loops']:
            var_name = loop['var_name']  # 'item'

            # Extrair campos do loop
            fields = extract_item_fields(loop['content'], var_name)

            for field in fields:
                value = item_data.get(field, '')

                # Criar request de substituição
                # IMPORTANTE: Usar replaceAllText com matchCase para evitar substituições indesejadas
                requests.append({
                    'replaceAllText': {
                        'containsText': {
                            'text': f'{{{{{var_name}.{field}}}}}',
                            'matchCase': True,
                        },
                        'replaceText': str(value) if value is not None else '',
                    }
                })

    # 3. Remover tags {{FOR}} e {{END FOR}}
    # Usar regex pattern para remover todas as variações
    requests.append({
        'replaceAllText': {
            'containsText': {
                'text': '{{FOR',
                'matchCase': False,
            },
            'replaceText': '',
        }
    })
    requests.append({
        'replaceAllText': {
            'containsText': {
                'text': '}}',
                'matchCase': False,
            },
            'replaceText': '',
        }
    })
    requests.append({
        'replaceAllText': {
            'containsText': {
                'text': '{{END FOR}}',
                'matchCase': False,
            },
            'replaceText': '',
        }
    })

    return requests


def clean_loop_markers(requests: List[Dict]) -> List[Dict]:
    """
    Adiciona requests para remover marcadores de loop restantes.

    Args:
        requests: Lista de requests existentes

    Returns:
        Lista com requests adicionais para limpeza
    """
    cleanup_requests = [
        {
            'replaceAllText': {
                'containsText': {
                    'text': '{{FOR',
                    'matchCase': False,
                },
                'replaceText': '',
            }
        },
        {
            'replaceAllText': {
                'containsText': {
                    'text': 'IN',
                    'matchCase': False,
                },
                'replaceText': '',
            }
        },
        {
            'replaceAllText': {
                'containsText': {
                    'text': '{{END FOR}}',
                    'matchCase': False,
                },
                'replaceText': '',
            }
        },
    ]

    return requests + cleanup_requests
