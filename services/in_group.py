from models.user import User
from services.access_rule import AccessRule


class InGroup(AccessRule):
    """An account that is a member of one of these groups, named by the code an operator gave each group in the panel, so naming none lets nobody in."""

    def __init__(self, *codes: str):
        self.codes = frozenset(codes)

    def groups_named(self) -> frozenset[str]:
        return self.codes

    def permits(self, user: User | None, groups: frozenset[str]) -> bool:
        return user is not None and not self.codes.isdisjoint(groups)
