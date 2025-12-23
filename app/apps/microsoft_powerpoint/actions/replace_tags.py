"""Replace Tags Action - Microsoft PowerPoint."""

from typing import Dict, Any
import httpx


async def run(http_client: httpx.AsyncClient, parameters: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    presentation_id = parameters.get('presentation_id')
    replacements = parameters.get('replacements', {})

    if not presentation_id:
        raise ValueError("presentation_id is required")

    from app.services.document_generation.microsoft_powerpoint import MicrosoftPowerPointService
    from app.models import DataSourceConnection

    connection_id = context.auth.connection_id if context and hasattr(context, 'auth') and context.auth else None

    if connection_id:
        connection = DataSourceConnection.query.get(connection_id)
        if connection:
            service = MicrosoftPowerPointService(connection.get_credentials())
            service.replace_tags_in_presentation(presentation_id, replacements)
            return {'presentation_id': presentation_id, 'replacements_count': len(replacements), 'status': 'success'}

    return {'presentation_id': presentation_id, 'status': 'error', 'message': 'Connection not found'}
