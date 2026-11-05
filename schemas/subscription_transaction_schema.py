from datetime import datetime
from decimal import Decimal

from enums.normalized_action import NormalizedAction
from enums.webhook_event_status import WebhookEventStatus
from schemas.base_schema import BaseSchema


class SubscriptionTransactionSchema(BaseSchema):
    """What the provider reported: the amount is in the currency the buyer paid, which the store decides and not the plan."""

    id: int
    action: NormalizedAction | None
    status: WebhookEventStatus
    amount: Decimal | None
    currency: str | None
    occurred_at: datetime | None
    created_at: datetime
