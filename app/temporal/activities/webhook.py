"""
Activity de Webhook Output - Envia POST com resultado da execução.
"""
import logging
import json
from typing import Dict, Any
from temporalio import activity
import requests

logger = logging.getLogger(__name__)


@activity.defn
async def execute_webhook_node(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa node de webhook (envia POST com resultado da execução).
    
    Args:
        data: {
            execution_id,
            node: {id, node_type, config, ...},
            execution_context: {
                source_data,
                generated_documents,
                signature_requests,
                ...
            }
        }
    
    Returns:
        {success: bool, status_code: int, response_body: str}
    """
    node = data['node']
    config = node.get('config', {})
    url = config.get('url')
    method = config.get('method', 'POST').upper()
    headers = config.get('headers', {})
    body_template = config.get('body_template')
    timeout = config.get('timeout', 30)
    
    if not url:
        raise ValueError('url não configurado no Webhook node')
    
    # Preparar body com execution_context
    execution_context = data.get('execution_context', {})
    
    # Body padrão com execution_context
    default_body = {
        'workflow_id': execution_context.get('workflow_id'),
        'execution_id': data['execution_id'],
        'source_data': execution_context.get('source_data', {}),
        'generated_documents': execution_context.get('generated_documents', []),
        'signature_requests': execution_context.get('signature_requests', []),
        'metadata': execution_context.get('metadata', {})
    }
    
    # Se body_template fornecido, processar template
    if body_template:
        try:
            # Substituir placeholders no template com dados do context
            from app.services.document_generation.tag_processor import TagProcessor
            
            # Criar contexto completo para substituição
            tag_context = {
                'source_data': execution_context.get('source_data', {}),
                'generated_documents': execution_context.get('generated_documents', []),
                'signature_requests': execution_context.get('signature_requests', []),
                'metadata': execution_context.get('metadata', {}),
                'workflow_id': execution_context.get('workflow_id'),
                'execution_id': data['execution_id']
            }
            
            # Processar template
            processed_body = TagProcessor.replace_tags(body_template, tag_context)
            
            # Se template retorna string JSON, parsear
            if isinstance(processed_body, str):
                try:
                    body = json.loads(processed_body)
                except json.JSONDecodeError:
                    # Se não é JSON válido, usar como string
                    body = processed_body
            else:
                body = processed_body
        except Exception as e:
            activity.logger.warning(f"Erro ao processar body_template: {e}. Usando body padrão.")
            body = default_body
    else:
        body = default_body
    
    # Garantir que headers incluem Content-Type se não especificado
    if 'Content-Type' not in headers:
        headers['Content-Type'] = 'application/json'
    
    # Enviar webhook
    try:
        response = requests.request(
            method=method,
            url=url,
            json=body if isinstance(body, dict) else None,
            data=body if isinstance(body, str) else None,
            headers=headers,
            timeout=timeout
        )
        response.raise_for_status()
        
        activity.logger.info(
            f"Webhook enviado com sucesso: {url} retornou {response.status_code}"
        )
        
        # Limitar tamanho da resposta para logging
        response_body = response.text[:500] if response.text else ''
        
        return {
            'success': True,
            'status_code': response.status_code,
            'response_body': response_body
        }
    except requests.exceptions.Timeout:
        activity.logger.error(f"Timeout ao enviar webhook {url} (timeout: {timeout}s)")
        raise Exception(f'Timeout ao enviar webhook: {url}')
    except requests.exceptions.RequestException as e:
        activity.logger.error(f"Erro ao enviar webhook {url}: {str(e)}")
        raise Exception(f'Erro ao enviar webhook: {str(e)}')
    except Exception as e:
        activity.logger.error(f"Erro inesperado ao enviar webhook {url}: {str(e)}")
        raise
