from datetime import datetime

from enums.app_event_status import AppEventStatus
from schemas.tenant_reference import TenantReference
from schemas.timestamp_schema import TimestampSchema
from schemas.user_reference import UserReference


class AppEventSchema(TimestampSchema):
    id: int
    tenant_id: int | None
    tenant: TenantReference | None
    user_id: int | None
    user: UserReference | None
    uuid: str
    name: str
    params: dict
    occurred_at: datetime
    status: AppEventStatus
    attempts: int
    error_code: str | None
    error_message: str | None
    processed_at: datetime | None
