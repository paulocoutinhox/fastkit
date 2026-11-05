from datetime import datetime

from enums.user_entitlement_status import UserEntitlementStatus
from schemas.entitlement_reference import EntitlementReference
from schemas.subscription_reference import SubscriptionReference
from schemas.timestamp_schema import TimestampSchema


class UserEntitlementSchema(TimestampSchema):
    id: int
    subscription_id: int
    subscription: SubscriptionReference | None
    entitlement_id: int
    entitlement: EntitlementReference | None
    status: UserEntitlementStatus
    started_at: datetime | None
    expires_at: datetime | None
    revoked_at: datetime | None
    meta: dict
