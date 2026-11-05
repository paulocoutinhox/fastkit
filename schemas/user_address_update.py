from schemas.common import as_optional
from schemas.user_address_create import UserAddressCreate

UserAddressUpdate = as_optional("UserAddressUpdate", UserAddressCreate)
