from enum import StrEnum


class UserRole(StrEnum):
    NORMAL = "normal"
    EDITOR = "editor"
    ADMINISTRATOR = "administrator"


# Who works in the panel, named one by one: derived as every role but one, a role added later would reach it the day it is written.
PANEL_ROLES = (UserRole.EDITOR, UserRole.ADMINISTRATOR)


class UserGender(StrEnum):
    MALE = "male"
    FEMALE = "female"
    NONE = "none"


class UserStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    BLOCKED = "blocked"
    ERASED = "erased"


class UserAddressType(StrEnum):
    MAIN = "main"
    BILLING = "billing"
    SHIPPING = "shipping"
