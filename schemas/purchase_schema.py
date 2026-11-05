from datetime import datetime
from decimal import Decimal

from enums.purchase_status import PurchaseStatus
from schemas.product_reference import ProductReference
from schemas.tenant_reference import TenantReference
from schemas.timestamp_schema import TimestampSchema
from schemas.user_reference import UserReference


class PurchaseSchema(TimestampSchema):
    id: int
    tenant_id: int | None
    tenant: TenantReference | None
    user_id: int
    user: UserReference | None
    product_id: int
    product: ProductReference | None
    integration_id: int | None
    reference: str
    external_id: str | None
    currency: str
    price: Decimal
    status: PurchaseStatus
    paid_at: datetime | None
    meta: dict
