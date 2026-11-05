from models.user import User
from services.access_rule import AccessRule


class AllOf(AccessRule):
    """Whoever every one of these rules lets in."""

    def __init__(self, *rules: AccessRule):
        # Every rule of nothing is true of everybody, so a combination written empty would open the door instead of closing it.
        if not rules:
            raise ValueError("every one of no rules lets everybody in")

        self.rules = rules

    def groups_named(self) -> frozenset[str]:
        return frozenset().union(*(rule.groups_named() for rule in self.rules))

    def permits(self, user: User | None, groups: frozenset[str]) -> bool:
        return all(rule.permits(user, groups) for rule in self.rules)
