"""Send Email Action - Gmail."""

from typing import Dict, Any
import httpx


async def run(http_client: httpx.AsyncClient, parameters: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    """Sends email via Gmail SMTP using existing EmailService."""
    from app.services.email_service import EmailService
    from app.models import DataSourceConnection

    to = parameters.get('to', [])
    cc = parameters.get('cc', [])
    bcc = parameters.get('bcc', [])
    subject = parameters.get('subject', '')
    body = parameters.get('body', '')
    body_type = parameters.get('body_type', 'html')
    attachments = parameters.get('attachments', [])

    connection_id = context.auth.connection_id if context and hasattr(context, 'auth') and context.auth else None

    if not connection_id:
        raise ValueError("connection_id is required")

    connection = DataSourceConnection.query.get(connection_id)
    if not connection:
        raise ValueError(f"Connection {connection_id} not found")

    credentials = connection.get_credentials()
    email_service = EmailService()

    result = email_service.send_via_smtp(
        credentials=credentials,
        to=to if isinstance(to, list) else [to],
        cc=cc if isinstance(cc, list) else ([cc] if cc else []),
        bcc=bcc if isinstance(bcc, list) else ([bcc] if bcc else []),
        subject=subject,
        body=body,
        body_type=body_type,
        attachments=attachments,
    )

    return {
        'status': 'sent' if result.get('success') else 'failed',
        'message_id': result.get('message_id'),
        'recipients': to,
    }
