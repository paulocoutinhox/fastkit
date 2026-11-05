from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from helpers.database_base import Base
from models.content import Content
from models.identified_mixin import BigId, IdentifiedMixin
from models.timestamp_mixin import TimestampMixin
from models.user_group import UserGroup


class ContentGroup(Base, IdentifiedMixin, TimestampMixin):
    __tablename__ = "content_group"
    __table_args__ = (UniqueConstraint("content_id", "group_id", name="content_group_unique"),)

    content_id: Mapped[int] = mapped_column(BigId, ForeignKey("content.id", ondelete="CASCADE"), nullable=False)
    group_id: Mapped[int] = mapped_column(BigId, ForeignKey("user_group.id", ondelete="CASCADE"), nullable=False)

    content: Mapped[Content] = relationship(Content)
    group: Mapped[UserGroup] = relationship(UserGroup)
