from models.user import User
from services.access_rule import AccessRule


class Everyone(AccessRule):
    """Anybody at all, signed in or not."""

    def permits(self, user: User | None, groups: frozenset[str]) -> bool:
        return True
