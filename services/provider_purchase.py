from dataclasses import dataclass
from datetime import datetime

from enums.environment import Environment
from enums.subscription_status import SubscriptionStatus


@dataclass(frozen=True)
class ProviderPurchase:
    """One line of what a provider says an account holds right now, recurring or bought once."""

    external_id: str
    product_reference: str
    store: str | None = None
    ownership: str | None = None
    period_type: str | None = None
    trial: bool = False
    purchased_at: datetime | None = None
    first_purchased_at: datetime | None = None
    period_ends_at: datetime | None = None
    grace_ends_at: datetime | None = None
    auto_resume_at: datetime | None = None
    unsubscribed_at: datetime | None = None
    refunded_at: datetime | None = None
    environment: Environment = Environment.PRODUCTION
    recurring: bool = True

    # What the gateway calls this state, for the ones that name it instead of leaving it to be read off the dates.
    status: SubscriptionStatus | None = None
