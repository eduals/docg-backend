"""
New Response Trigger - Processa novas respostas de Google Forms.
"""

from typing import Dict, Any
import httpx


async def run(http_client: httpx.AsyncClient, trigger_data: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    """
    Processa trigger de nova resposta de formulário.

    Args:
        http_client: Cliente HTTP configurado
        trigger_data: Dados do webhook ou resposta
        context: GlobalVariable context

    Returns:
        Dict com dados da resposta normalizada
    """
    form_id = trigger_data.get('form_id')
    response_id = trigger_data.get('response_id')

    if form_id and response_id:
        # Buscar resposta completa
        try:
            response = await http_client.get(
                f'https://forms.googleapis.com/v1/forms/{form_id}/responses/{response_id}'
            )
            response.raise_for_status()
            data = response.json()

            # Normalizar respostas
            answers = {}
            for question_id, answer in data.get('answers', {}).items():
                text_answers = answer.get('textAnswers', {}).get('answers', [])
                if text_answers:
                    answers[question_id] = text_answers[0].get('value', '')

            return {
                'response_id': data.get('responseId'),
                'create_time': data.get('createTime'),
                'answers': answers,
                'raw': data,
            }
        except Exception as e:
            pass

    # Retornar dados como recebidos
    return {
        'response': trigger_data,
        'source': 'google-forms',
    }
