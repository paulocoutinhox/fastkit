from helpers.crud import build_router
from schemas.user_address_create import UserAddressCreate
from schemas.user_address_schema import UserAddressSchema
from schemas.user_address_update import UserAddressUpdate
from schemas.user_create import UserCreate
from schemas.user_schema import UserSchema
from schemas.user_update import UserUpdate
from services.user_address_service import user_address_service
from services.user_service import user_service

router = build_router(user_service, UserSchema, UserCreate, UserUpdate, "/users", "users")
address_router = build_router(user_address_service, UserAddressSchema, UserAddressCreate, UserAddressUpdate, "/user-addresses", "user addresses")
