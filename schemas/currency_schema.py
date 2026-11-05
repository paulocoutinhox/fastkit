from schemas.tenant_reference import TenantReference
from schemas.timestamp_schema import TimestampSchema


class CurrencySchema(TimestampSchema):
    id: int
    uuid: str
    tenant_id: int | None
    tenant: TenantReference | None
    code: str
    name: str
    symbol: str | None
    position: int
    active: bool
    meta: dict
