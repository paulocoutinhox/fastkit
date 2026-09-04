from pydantic import EmailStr, Field

from schemas.common import BaseSchema, Text, TimestampSchema, as_optional


class TenantReference(BaseSchema):
    id: int
    code: str
    name: str


class TenantSchema(TimestampSchema):
    id: int
    code: str
    name: str
    domain: str
    email_contact: str | None
    email_administrative: str | None
    active: bool
    meta: dict


class TenantCreate(BaseSchema):
    code: str | None = Field(None, max_length=64)
    name: Text(128)
    domain: Text(255)
    email_contact: EmailStr | None = Field(None, max_length=255)
    email_administrative: EmailStr | None = Field(None, max_length=255)
    active: bool = True
    meta: dict = Field(default_factory=dict)


TenantUpdate = as_optional("TenantUpdate", TenantCreate)
