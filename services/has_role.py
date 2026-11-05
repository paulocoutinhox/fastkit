from enums.user_role import UserRole
from models.user import User
from services.access_rule import AccessRule


class HasRole(AccessRule):
    """An account holding one of these roles, read from the account and never from the token it signed in with."""

    def __init__(self, *roles: UserRole):
        self.roles = frozenset(roles)

    def permits(self, user: User | None, groups: frozenset[str]) -> bool:
        return user is not None and user.role in self.roles
