from pydantic import Field

from schemas.base_schema import BaseSchema
from schemas.common import Text


class AddressFields(BaseSchema):
    """What an address is, written once for the operator and for the account, because the copy on one side is the one that stops refusing a blank line."""

    line1: Text(255)
    street_number: str | None = Field(None, max_length=32)
    complement: str | None = Field(None, max_length=255)
    district: str | None = Field(None, max_length=128)
    city: Text(128)
    state: Text(128)
    postal_code: Text(32)
    country_code: str = Field(min_length=2, max_length=2)
