from datetime import datetime

from enums.user_entitlement_status import UserEntitlementStatus
from schemas.base_schema import BaseSchema


class AccountEntitlementSchema(BaseSchema):
    """What the signed in account holds, keyed by the code an app gates a feature with."""

    code: str
    name: str
    status: UserEntitlementStatus
    started_at: datetime | None
    expires_at: datetime | None
