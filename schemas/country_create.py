from pydantic import Field

from enums.postal_code_provider import PostalCodeProvider
from schemas.base_schema import BaseSchema
from schemas.common import Text


class CountryCreate(BaseSchema):
    name: Text(128)
    code_iso_3166_1: Text(2)
    postal_code_provider: PostalCodeProvider | None = None
    phone_mask: str | None = Field(None, max_length=32)
    active: bool = True
