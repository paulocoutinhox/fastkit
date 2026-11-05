from enums.postal_code_provider import PostalCodeProvider
from schemas.timestamp_schema import TimestampSchema


class CountrySchema(TimestampSchema):
    id: int
    name: str
    code_iso_3166_1: str
    postal_code_provider: PostalCodeProvider | None
    phone_mask: str | None
    active: bool
