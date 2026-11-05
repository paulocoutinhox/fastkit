from datetime import datetime
from decimal import Decimal

from enums.purchase_status import PurchaseStatus
from schemas.product_reference import ProductReference
from schemas.timestamp_schema import TimestampSchema


class AccountPurchaseSchema(TimestampSchema):
    """The statement of whoever is asking, so naming the account on every line would say nothing."""

    id: int
    product: ProductReference
    reference: str
    currency: str
    price: Decimal
    status: PurchaseStatus
    paid_at: datetime | None
