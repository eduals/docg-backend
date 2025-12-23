"""Process AI Tags Action - Process {{ai:tag}} in text."""

from typing import Dict, Any
import httpx
import re


async def run(http_client: httpx.AsyncClient, parameters: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    from app.services.ai.llm_service import LLMService

    text = parameters.get('text', '')
    mappings = parameters.get('mappings', {})
    model = parameters.get('model', 'gpt-4')
    api_key = parameters.get('api_key')

    if not text:
        return {'text': text, 'processed': 0}

    # Find all {{ai:tag}} patterns
    pattern = r'\{\{ai:([^}]+)\}\}'
    matches = re.findall(pattern, text)

    if not matches:
        return {'text': text, 'processed': 0}

    llm = LLMService(api_key=api_key)
    processed = 0

    for tag in matches:
        if tag in mappings:
            mapping = mappings[tag]
            prompt = mapping.get('prompt', '')
            if prompt:
                response = await llm.async_complete(prompt=prompt, model=model)
                text = text.replace(f'{{{{ai:{tag}}}}}', response.content)
                processed += 1

    return {'text': text, 'processed': processed}
