"""Send Email Action - Outlook via Microsoft Graph."""

from typing import Dict, Any
import httpx


async def run(http_client: httpx.AsyncClient, parameters: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    to = parameters.get('to', [])
    cc = parameters.get('cc', [])
    subject = parameters.get('subject', '')
    body = parameters.get('body', '')
    body_type = parameters.get('body_type', 'html')

    if isinstance(to, str):
        to = [to]

    recipients = [{'emailAddress': {'address': email}} for email in to]
    cc_recipients = [{'emailAddress': {'address': email}} for email in (cc if isinstance(cc, list) else [cc] if cc else [])]

    message = {
        'message': {
            'subject': subject,
            'body': {'contentType': 'HTML' if body_type == 'html' else 'Text', 'content': body},
            'toRecipients': recipients,
            'ccRecipients': cc_recipients,
        }
    }

    response = await http_client.post('/me/sendMail', json=message)
    response.raise_for_status()

    return {'status': 'sent', 'recipients': to}
