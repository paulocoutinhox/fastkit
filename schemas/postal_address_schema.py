from schemas.base_schema import BaseSchema


class PostalAddressSchema(BaseSchema):
    """What a postal code stands for, in the shape the address of an account is written in."""

    line1: str
    district: str
    city: str
    state: str
