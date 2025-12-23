"""
Export PDF Action - Exporta documento Google Docs como PDF.
"""

from typing import Dict, Any
import httpx


async def run(
    http_client: httpx.AsyncClient,
    parameters: Dict[str, Any],
    context: Any = None,
) -> Dict[str, Any]:
    """
    Exporta documento como PDF.

    Args:
        http_client: Cliente HTTP configurado
        parameters: {
            'document_id': 'ID do documento',
            'save_to_drive': True (optional),
            'folder_id': 'pasta destino' (optional)
        }
        context: GlobalVariable context

    Returns:
        Dict com URL do PDF
    """
    document_id = parameters.get('document_id')
    save_to_drive = parameters.get('save_to_drive', False)
    folder_id = parameters.get('folder_id')

    if not document_id:
        raise ValueError("document_id is required")

    drive_url = 'https://www.googleapis.com/drive/v3'

    # Exportar como PDF
    response = await http_client.get(
        f'{drive_url}/files/{document_id}/export',
        params={'mimeType': 'application/pdf'}
    )
    response.raise_for_status()

    pdf_content = response.content

    result = {
        'document_id': document_id,
        'pdf_size': len(pdf_content),
        'status': 'exported',
    }

    if save_to_drive:
        # Obter nome do documento original
        meta_response = await http_client.get(
            f'{drive_url}/files/{document_id}',
            params={'fields': 'name'}
        )
        doc_name = meta_response.json().get('name', 'document')

        # Upload do PDF
        import io
        from httpx import MultipartFiles

        files = {
            'metadata': ('metadata', '{"name": "' + doc_name + '.pdf", "mimeType": "application/pdf"}', 'application/json'),
            'file': ('file.pdf', pdf_content, 'application/pdf'),
        }

        # Upload simples
        upload_response = await http_client.post(
            f'{drive_url}/files?uploadType=multipart',
            files=files
        )

        if upload_response.status_code == 200:
            pdf_data = upload_response.json()
            result['pdf_id'] = pdf_data.get('id')
            result['pdf_url'] = f"https://drive.google.com/file/d/{pdf_data.get('id')}/view"

    return result
