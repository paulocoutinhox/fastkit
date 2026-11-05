from enums.user_address_type import UserAddressType
from schemas.timestamp_schema import TimestampSchema
from schemas.user_reference import UserReference


class UserAddressSchema(TimestampSchema):
    id: int
    user_id: int
    user: UserReference | None
    type: UserAddressType
    line1: str
    street_number: str | None
    complement: str | None
    district: str | None
    city: str
    state: str
    postal_code: str
    country_code: str
    meta: dict
