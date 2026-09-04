from datetime import datetime

from pydantic import Field

from enums.event import AppEventStatus
from schemas.common import BaseSchema, TimestampSchema
from schemas.tenant import TenantReference
from schemas.user import UserReference


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


class AppEventInput(BaseSchema):
    uuid: str = Field(max_length=36)
    name: str = Field(max_length=128)
    params: dict = Field(default_factory=dict)
    occurred_at: datetime


class AppEventBatchRequest(BaseSchema):
    events: list[AppEventInput] = Field(min_length=1, max_length=100)


class AppEventBatchResponse(BaseSchema):
    accepted: int
    duplicated: int
