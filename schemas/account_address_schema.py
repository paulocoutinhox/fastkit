from enums.user_address_type import UserAddressType
from schemas.timestamp_schema import TimestampSchema


class AccountAddressSchema(TimestampSchema):
    """The address of whoever is asking, so naming the account on it would say nothing."""

    id: int
    type: UserAddressType
    line1: str
    street_number: str | None
    complement: str | None
    district: str | None
    city: str
    state: str
    postal_code: str
    country_code: str
