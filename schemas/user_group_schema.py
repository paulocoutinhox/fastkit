from schemas.tenant_reference import TenantReference
from schemas.timestamp_schema import TimestampSchema


class UserGroupSchema(TimestampSchema):
    id: int
    tenant_id: int | None
    tenant: TenantReference | None
    code: str
    name: str
    active: bool
