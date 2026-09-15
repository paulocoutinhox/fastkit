from pydantic import EmailStr, Field

from schemas.common import BaseSchema, Domain, JsonMap, Text, TimestampSchema, as_optional


class TenantReference(BaseSchema):
    id: int
    code: str
    name: str
    domain: str


class TenantSchema(TimestampSchema):
    id: int
    code: str
    name: str
    domain: str
    email_contact: str
    active: bool
    meta: dict


class TenantCreate(BaseSchema):
    code: str | None = Field(None, max_length=64)
    name: Text(128)
    domain: Domain
    email_contact: EmailStr = Field(min_length=3, max_length=255)
    active: bool = True
    meta: JsonMap = Field(default_factory=dict)


TenantUpdate = as_optional("TenantUpdate", TenantCreate)
