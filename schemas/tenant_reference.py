from schemas.base_schema import BaseSchema


class TenantReference(BaseSchema):
    id: int
    code: str
    name: str
    domain: str
