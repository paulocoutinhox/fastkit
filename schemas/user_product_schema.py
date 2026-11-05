from datetime import datetime

from schemas.product_reference import ProductReference
from schemas.timestamp_schema import TimestampSchema
from schemas.user_reference import UserReference


class UserProductSchema(TimestampSchema):
    id: int
    user_id: int
    user: UserReference | None
    product_id: int
    product: ProductReference | None
    purchase_id: int | None
    subscription_id: int | None
    benefit_grant_id: int | None
    granted_at: datetime
    meta: dict
