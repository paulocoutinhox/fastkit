from enums.normalized_action import NormalizedAction
from enums.webhook_event_status import WebhookEventStatus
from schemas.base_schema import BaseSchema


class WebhookReceipt(BaseSchema):
    """What the provider reads back: whether the event was taken, ignored or already known."""

    status: WebhookEventStatus
    action: NormalizedAction | None
