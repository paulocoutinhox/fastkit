from sqlalchemy import ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from helpers.database_base import Base
from models.identified_mixin import BigId, IdentifiedMixin
from models.timestamp_mixin import TimestampMixin
from models.user import User
from models.user_group import UserGroup


class UserGroupMember(Base, IdentifiedMixin, TimestampMixin):
    __tablename__ = "user_group_member"
    # Every access check asks which groups one account is a member of, so the account is the column this table is read by.
    __table_args__ = (UniqueConstraint("group_id", "user_id", name="user_group_member_unique"), Index("user_group_member_user", "user_id"))

    group_id: Mapped[int] = mapped_column(BigId, ForeignKey("user_group.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(BigId, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)

    group: Mapped[UserGroup] = relationship(UserGroup)
    user: Mapped[User] = relationship(User)
