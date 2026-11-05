from pydantic import Field

from enums.user_address_type import UserAddressType
from schemas.address_fields import AddressFields
from schemas.common import JsonMap, Reference


class UserAddressCreate(AddressFields):
    user_id: Reference
    type: UserAddressType = UserAddressType.MAIN
    meta: JsonMap = Field(default_factory=dict)
