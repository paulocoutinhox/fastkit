from models.user import User
from services.access_rule import AccessRule


class SignedIn(AccessRule):
    """Any signed in account, whatever its role and its groups."""

    def permits(self, user: User | None, groups: frozenset[str]) -> bool:
        return user is not None
