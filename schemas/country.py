from pydantic import Field

from enums.country import PostalCodeProvider
from schemas.common import BaseSchema, Text, TimestampSchema, as_optional


class CountrySchema(TimestampSchema):
    id: int
    name: str
    code_iso_3166_1: str
    postal_code_provider: PostalCodeProvider | None
    phone_mask: str | None
    active: bool


class CountryCreate(BaseSchema):
    name: Text(128)
    code_iso_3166_1: Text(2)
    postal_code_provider: PostalCodeProvider | None = None
    phone_mask: str | None = Field(None, max_length=32)
    active: bool = True


CountryUpdate = as_optional("CountryUpdate", CountryCreate)


class OfferedCountrySchema(BaseSchema):
    """What an address form is offered, where the provider is what says the postal code can be looked up."""

    code_iso_3166_1: str
    name: str
    postal_code_provider: PostalCodeProvider | None
    phone_mask: str | None


class PostalAddressSchema(BaseSchema):
    """What a postal code stands for, in the shape the address of an account is written in."""

    line1: str
    district: str
    city: str
    state: str
