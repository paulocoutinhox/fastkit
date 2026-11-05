from datetime import datetime

from enums.benefit_grant_status import BenefitGrantStatus
from schemas.timestamp_schema import TimestampSchema


class BenefitGrantSchema(TimestampSchema):
    id: int
    subscription_benefit_id: int
    grant_key: str
    cycle_key: str
    scheduled_at: datetime
    status: BenefitGrantStatus
    requested_quantity: int
    granted_quantity: int
    result: dict
    error_code: str | None
    error_message: str | None
    attempts: int
    started_at: datetime | None
    completed_at: datetime | None
    meta: dict
