from enum import StrEnum


class UserRole(StrEnum):
    NORMAL = "normal"
    EDITOR = "editor"
    ADMINISTRATOR = "administrator"
