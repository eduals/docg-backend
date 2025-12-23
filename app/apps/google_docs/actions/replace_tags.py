"""
Replace Tags Action - Substitui tags em documento Google Docs.

Feature 3: Suporte a loops em tabelas
Sintaxe: {{FOR item IN array}}...{{END FOR}}
"""

from typing import Dict, Any, List
import httpx


async def run(
    http_client: httpx.AsyncClient,
    parameters: Dict[str, Any],
    context: Any = None,
) -> Dict[str, Any]:
    """
    Substitui {{tags}} em um documento.

    Suporta:
    - Tags simples: {{field}} ou {{step.abc.field}}
    - Loops em tabelas: {{FOR item IN array}}{{item.field}}{{END FOR}}

    Args:
        http_client: Cliente HTTP configurado
        parameters: {
            'document_id': 'ID do documento',
            'replacements': {'tag': 'valor', ...}
        }
        context: GlobalVariable context

    Returns:
        Dict com status da substituição
    """
    document_id = parameters.get('document_id')
    replacements = parameters.get('replacements', {})

    if not document_id:
        raise ValueError("document_id is required")

    requests: List[Dict] = []
    loops_processed = 0

    # 1. Obter documento para detectar loops
    doc_response = await http_client.get(
        f'https://docs.googleapis.com/v1/documents/{document_id}'
    )
    doc_response.raise_for_status()
    document = doc_response.json()

    # 2. Processar loops em tabelas (Feature 3)
    try:
        from app.services.document_generation.table_loops import (
            detect_table_loops,
            build_duplicate_row_requests
        )
        from app.services.document_generation.loop_parser import resolve_array

        table_loops = detect_table_loops(document)

        for table_loop in table_loops:
            for loop in table_loop['loops']:
                # Resolver array do contexto
                # Tentar primeiro em replacements, depois em context
                array_data = replacements.get(loop['array_path'], [])

                # Se não encontrou em replacements, tentar em context
                if not array_data and context:
                    # Construir contexto completo para resolver
                    full_context = {'replacements': replacements}
                    if hasattr(context, 'step') and hasattr(context.step, 'parameters'):
                        full_context['step'] = context.step.parameters

                    array_data = resolve_array(loop['array_path'], full_context)

                # Se ainda não encontrou, usar lista vazia
                if not isinstance(array_data, list):
                    array_data = []

                if array_data:
                    # Gerar requests para duplicar linhas
                    loop_requests = build_duplicate_row_requests(table_loop, array_data)
                    requests.extend(loop_requests)
                    loops_processed += 1

    except ImportError:
        # Se módulos de loop não disponíveis, continuar sem loops
        pass
    except Exception as e:
        # Log error mas não falhar a substituição
        print(f"Warning: Error processing loops: {e}")

    # 3. Processar tags normais
    for tag, value in replacements.items():
        # Pular arrays que foram processados como loops
        if isinstance(value, list):
            continue

        # Suportar tags com ou sem {{ }}
        search_text = tag if '{{' in tag else f'{{{{{tag}}}}}'

        requests.append({
            'replaceAllText': {
                'containsText': {
                    'text': search_text,
                    'matchCase': False,
                },
                'replaceText': str(value) if value is not None else '',
            }
        })

    # 4. Executar batchUpdate
    if requests:
        response = await http_client.post(
            f'https://docs.googleapis.com/v1/documents/{document_id}:batchUpdate',
            json={'requests': requests}
        )
        response.raise_for_status()

    return {
        'document_id': document_id,
        'replacements_count': len(replacements),
        'loops_processed': loops_processed,
        'status': 'success',
    }
