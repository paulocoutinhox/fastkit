from enums.system_log import LogCategory, LogLevel
from schemas.common import TimestampSchema
from schemas.tenant import TenantReference
from schemas.user import UserReference


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
