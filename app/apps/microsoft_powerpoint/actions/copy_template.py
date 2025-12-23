"""Copy Template Action - Microsoft PowerPoint."""

from typing import Dict, Any
import httpx


async def run(http_client: httpx.AsyncClient, parameters: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    item_id = parameters.get('item_id')
    name = parameters.get('name', 'Presentation Copy')

    if not item_id:
        raise ValueError("item_id is required")

    response = await http_client.post(f'/me/drive/items/{item_id}/copy', json={'name': name})

    if response.status_code == 202:
        return {'status': 'copying', 'monitor_url': response.headers.get('Location')}

    response.raise_for_status()
    data = response.json()

    return {'presentation_id': data.get('id'), 'name': data.get('name'), 'web_url': data.get('webUrl')}
