from enums.postal_code_provider import PostalCodeProvider
from schemas.base_schema import BaseSchema


class OfferedCountrySchema(BaseSchema):
    """What an address form is offered, where the provider is what says the postal code can be looked up."""

    code_iso_3166_1: str
    name: str
    postal_code_provider: PostalCodeProvider | None
    phone_mask: str | None
