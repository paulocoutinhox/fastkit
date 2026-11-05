from schemas.timestamp_schema import TimestampSchema


class TenantSchema(TimestampSchema):
    id: int
    code: str
    name: str
    domain: str
    email_contact: str
    active: bool
    meta: dict
