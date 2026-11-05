from models.user import User
from services.access_rule import AccessRule


class AnyOf(AccessRule):
    """Whoever any one of these rules lets in."""

    def __init__(self, *rules: AccessRule):
        self.rules = rules

    def groups_named(self) -> frozenset[str]:
        return frozenset().union(*(rule.groups_named() for rule in self.rules))

    def permits(self, user: User | None, groups: frozenset[str]) -> bool:
        return any(rule.permits(user, groups) for rule in self.rules)
