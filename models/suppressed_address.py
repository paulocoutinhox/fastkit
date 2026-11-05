from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from helpers.database_base import Base
from models.identified_mixin import IdentifiedMixin
from models.timestamp_mixin import TimestampMixin


class SuppressedAddress(Base, IdentifiedMixin, TimestampMixin):
    """An address a server refused for good, which nothing writes to again because sending there burns the reputation of the domain."""

    __tablename__ = "email_suppressed_address"
    __table_args__ = (UniqueConstraint("address", name="email_suppressed_address_unique"),)

    address: Mapped[str] = mapped_column(String(320), nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
