"""Generate Text Action - AI text generation."""

from typing import Dict, Any
import httpx


async def run(http_client: httpx.AsyncClient, parameters: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    from app.services.ai.llm_service import LLMService

    prompt = parameters.get('prompt', '')
    model = parameters.get('model', 'gpt-4')
    temperature = parameters.get('temperature', 0.7)
    max_tokens = parameters.get('max_tokens', 1000)
    api_key = parameters.get('api_key')

    if not prompt:
        raise ValueError("prompt is required")

    llm = LLMService(api_key=api_key)
    response = await llm.async_complete(prompt=prompt, model=model, temperature=temperature, max_tokens=max_tokens)

    return {
        'text': response.content,
        'model': model,
        'tokens_used': response.usage.get('total_tokens', 0) if response.usage else 0,
        'cost_usd': response.cost_usd,
    }
