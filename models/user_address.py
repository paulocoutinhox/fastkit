from sqlalchemy import JSON, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from enums.user_address_type import UserAddressType
from helpers.database_base import Base
from models.base import enum_type
from models.identified_mixin import BigId, IdentifiedMixin
from models.timestamp_mixin import TimestampMixin
from models.user import User


class UserAddress(Base, IdentifiedMixin, TimestampMixin):
    """One address per purpose, because a second `main` is two answers to the question the checkout asks once."""

    __tablename__ = "user_address"
    __table_args__ = (UniqueConstraint("user_id", "type", name="user_address_type"), Index("user_address_place", "country_code", "state", "city"))

    user_id: Mapped[int] = mapped_column(BigId, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)

    type: Mapped[UserAddressType] = mapped_column(enum_type(UserAddressType, 16), default=UserAddressType.MAIN, nullable=False)

    line1: Mapped[str] = mapped_column(String(255), nullable=False)
    street_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    complement: Mapped[str | None] = mapped_column(String(255), nullable=True)
    district: Mapped[str | None] = mapped_column(String(128), nullable=True)
    city: Mapped[str] = mapped_column(String(128), nullable=False)
    state: Mapped[str] = mapped_column(String(128), nullable=False)
    postal_code: Mapped[str] = mapped_column(String(32), nullable=False)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)

    meta: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)

    user: Mapped[User] = relationship(User)
