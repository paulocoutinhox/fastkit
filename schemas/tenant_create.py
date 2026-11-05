from pydantic import EmailStr, Field

from schemas.base_schema import BaseSchema
from schemas.common import Domain, JsonMap, Text


class TenantCreate(BaseSchema):
    code: str | None = Field(None, max_length=64)
    name: Text(128)
    domain: Domain
    email_contact: EmailStr = Field(min_length=3, max_length=255)
    active: bool = True
    meta: JsonMap = Field(default_factory=dict)
