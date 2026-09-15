from helpers.crud import build_router
from schemas.user import UserAddressCreate, UserAddressSchema, UserAddressUpdate, UserCreate, UserSchema, UserUpdate
from services.user import user_address_service, user_service

router = build_router(user_service, UserSchema, UserCreate, UserUpdate, "/users", "users")
address_router = build_router(user_address_service, UserAddressSchema, UserAddressCreate, UserAddressUpdate, "/user-addresses", "user addresses")
