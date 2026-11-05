from sqlalchemy import ForeignKey, Index, String, column, func
from sqlalchemy.orm import Mapped, mapped_column

from enums.social_provider import SocialProvider
from helpers.database_base import Base
from models.base import enum_type
from models.identified_mixin import BigId, IdentifiedMixin
from models.timestamp_mixin import TimestampMixin


class SocialIdentity(Base, IdentifiedMixin, TimestampMixin):
    __tablename__ = "social_identity"
    __table_args__ = (Index("social_identity_subject", func.coalesce(column("tenant_id"), 0), "provider", "subject", unique=True), Index("social_identity_user", "user_id", "provider", unique=True))

    tenant_id: Mapped[int | None] = mapped_column(BigId, ForeignKey("tenant.id", ondelete="CASCADE"), nullable=True)
    user_id: Mapped[int] = mapped_column(BigId, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[SocialProvider] = mapped_column(enum_type(SocialProvider), nullable=False)
    subject: Mapped[str] = mapped_column(String(255).with_variant(String(255, collation="utf8mb4_0900_bin"), "mysql"), nullable=False)
