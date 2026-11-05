from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from enums.normalized_action import NormalizedAction
from enums.purchase_status import PurchaseStatus
from services.provider_purchase import ProviderPurchase


@dataclass(frozen=True)
class ProviderEvent:
    """An event says which account to look at and what it was about, and never what the state became."""

    external_event_id: str
    event_type: str
    account_token: str | None = None
    product_reference: str | None = None
    action: NormalizedAction | None = None

    # Other accounts the notice moved something for, each asked about again, which is what a transfer between two accounts names.
    also_about: tuple[str, ...] = ()

    # What this notice resolved the account to hold, where nothing at all means the notice said nothing about that.
    state: tuple[ProviderPurchase, ...] | None = None

    # The reference this side minted before sending the buyer away, echoed back by the gateway, and what the gateway calls the payment it settled.
    reference: str | None = None
    purchase_status: PurchaseStatus | None = None
    payment_id: str | None = None

    amount: Decimal | None = None
    currency: str | None = None
    occurred_at: datetime | None = None
