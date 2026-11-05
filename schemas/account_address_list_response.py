from schemas.account_address_schema import AccountAddressSchema
from schemas.base_schema import BaseSchema


class AccountAddressListResponse(BaseSchema):
    items: list[AccountAddressSchema]
