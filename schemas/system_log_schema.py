from enums.log_category import LogCategory
from enums.log_level import LogLevel
from schemas.tenant_reference import TenantReference
from schemas.timestamp_schema import TimestampSchema
from schemas.user_reference import UserReference


class SystemLogSchema(TimestampSchema):
    id: int
    tenant_id: int | None
    tenant: TenantReference | None
    user_id: int | None
    user: UserReference | None
    level: LogLevel
    category: LogCategory | None
    description: str
    meta: dict
