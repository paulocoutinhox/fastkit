from schemas.tenant_reference import TenantReference
from schemas.timestamp_schema import TimestampSchema


class EntitlementSchema(TimestampSchema):
    id: int
    tenant_id: int | None
    tenant: TenantReference | None
    code: str
    name: str
    description: str | None
    active: bool
    meta: dict
