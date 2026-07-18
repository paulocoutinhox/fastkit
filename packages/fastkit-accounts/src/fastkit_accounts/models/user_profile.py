from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from fastkit_db.base import Base, MetadataMixin, PrimaryKeyMixin, TimestampMixin


class UserProfile(PrimaryKeyMixin, TimestampMixin, MetadataMixin, Base):
    __tablename__ = "user_profile"

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    avatar_file_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    bio: Mapped[str | None] = mapped_column(String(500), nullable=True)

    user: Mapped["User"] = relationship(back_populates="profile")
