from datetime import datetime

from sqlalchemy import JSON, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from enums.user_entitlement_status import UserEntitlementStatus
from helpers.database_base import Base
from models.base import enum_type
from models.entitlement import Entitlement
from models.identified_mixin import BigId, IdentifiedMixin
from models.subscription import Subscription
from models.timestamp_mixin import TimestampMixin
from models.utc_date_time import UtcDateTime


class UserEntitlement(Base, IdentifiedMixin, TimestampMixin):
    __tablename__ = "subscription_user_entitlement"
    __table_args__ = (UniqueConstraint("subscription_id", "entitlement_id", name="subscription_user_entitlement_unique"), Index("subscription_user_entitlement_lookup", "entitlement_id", "status", "expires_at"))

    subscription_id: Mapped[int] = mapped_column(BigId, ForeignKey("subscription.id", ondelete="CASCADE"), nullable=False)
    entitlement_id: Mapped[int] = mapped_column(BigId, ForeignKey("subscription_entitlement.id", ondelete="RESTRICT"), nullable=False)

    status: Mapped[UserEntitlementStatus] = mapped_column(enum_type(UserEntitlementStatus, 16), default=UserEntitlementStatus.ACTIVE, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    meta: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)

    subscription: Mapped[Subscription] = relationship(Subscription)
    entitlement: Mapped[Entitlement] = relationship(Entitlement)
