from abc import ABC, abstractmethod

from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User
from services.user_group_service import user_group_service


class AccessRule(ABC):
    """Who may reach something, which a report, a page or any other surface declares once and asks before it answers."""

    @abstractmethod
    def permits(self, user: User | None, groups: frozenset[str]) -> bool:
        """Whether this account, a member of these groups, is let in, where an anonymous visitor is no account at all."""

    def groups_named(self) -> frozenset[str]:
        """The groups this rule asks about, so a rule that names none never costs a query."""
        return frozenset()

    async def admits(self, db: AsyncSession, user: User | None) -> bool:
        groups = await user_group_service.codes_of(db, user) if user is not None and self.groups_named() else frozenset()

        return self.permits(user, groups)
