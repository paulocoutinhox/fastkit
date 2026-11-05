from schemas.common import as_optional
from schemas.user_create import UserCreate

UserUpdate = as_optional("UserUpdate", UserCreate)
