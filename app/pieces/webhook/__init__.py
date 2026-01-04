"""
Webhook Piece
Simple trigger that receives webhook calls
"""
from app.pieces.base import (
    Piece,
    Trigger,
    Action,
    ActionResult,
    Property,
    PropertyType,
    ExecutionContext,
    register_piece,
    short_text_property,
)


async def catch_webhook_handler(props: dict, ctx: ExecutionContext) -> ActionResult:
    """
    Webhook trigger handler
    The actual webhook catching is handled by the platform
    This just returns the webhook payload
    """
    # Webhook payload comes from trigger_output
    payload = ctx.trigger_output or {}

    return ActionResult(
        success=True,
        data=payload
    )


async def return_response_handler(props: dict, ctx: ExecutionContext) -> ActionResult:
    """
    Return a response to the webhook caller
    """
    status_code = props.get('status_code', 200)
    body = props.get('body', {})
    headers = props.get('headers', {})

    return ActionResult(
        success=True,
        data={
            'status_code': status_code,
            'body': body,
            'headers': headers
        }
    )


# Define the Webhook piece
webhook_piece = Piece(
    name="webhook",
    display_name="Webhook",
    description="Receive HTTP webhooks and respond",
    version="1.0.0",
    auth=None,  # No authentication required
    categories=["Core", "Triggers"],
    triggers=[
        Trigger(
            name="catch_webhook",
            display_name="Catch Webhook",
            description="Triggers when a webhook is received",
            type="WEBHOOK",
            properties=[],
            handler=catch_webhook_handler,
            sample_data={
                "body": {"example": "data"},
                "headers": {"content-type": "application/json"},
                "query": {}
            }
        )
    ],
    actions=[
        Action(
            name="return_response",
            display_name="Return Response",
            description="Return a custom response to the webhook caller",
            require_auth=False,
            properties=[
                Property(
                    name="status_code",
                    display_name="Status Code",
                    description="HTTP status code",
                    type=PropertyType.NUMBER,
                    default_value=200
                ),
                Property(
                    name="body",
                    display_name="Response Body",
                    description="JSON response body",
                    type=PropertyType.JSON,
                    required=True
                ),
                Property(
                    name="headers",
                    display_name="Headers",
                    description="Response headers",
                    type=PropertyType.OBJECT,
                    required=False
                )
            ],
            handler=return_response_handler
        )
    ]
)

# Register the piece
register_piece(webhook_piece)
