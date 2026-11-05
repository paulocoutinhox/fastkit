from schemas.tenant_reference import TenantReference
from schemas.timestamp_schema import TimestampSchema


class ContentCategorySchema(TimestampSchema):
    id: int
    uuid: str
    tenant_id: int | None
    tenant: TenantReference | None
    name: str
    tag: str
    active: bool
