from datetime import datetime

from sqlalchemy import JSON, BigInteger, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from enums.benefit_grant_status import BenefitGrantStatus
from helpers.database_base import Base
from models.base import enum_type
from models.identified_mixin import BigId, IdentifiedMixin
from models.subscription_benefit import SubscriptionBenefit
from models.timestamp_mixin import TimestampMixin
from models.utc_date_time import UtcDateTime


class BenefitGrant(Base, IdentifiedMixin, TimestampMixin):
    """One delivery attempt of one cycle, made idempotent by `grant_key` so a replay never hands the same thing out twice."""

    __tablename__ = "subscription_benefit_grant"
    __table_args__ = (
        UniqueConstraint("grant_key", name="subscription_benefit_grant_key"),
        UniqueConstraint("subscription_benefit_id", "cycle_key", name="subscription_benefit_grant_cycle"),
        UniqueConstraint("user_benefit_key", name="subscription_benefit_grant_user_benefit"),
        Index("subscription_benefit_grant_status", "status", "created_at"),
    )

    subscription_benefit_id: Mapped[int] = mapped_column(BigId, ForeignKey("subscription_benefit.id", ondelete="CASCADE"), nullable=False)

    grant_key: Mapped[str] = mapped_column(String(191), nullable=False)
    user_benefit_key: Mapped[str | None] = mapped_column(String(191), nullable=True)
    cycle: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cycle_key: Mapped[str] = mapped_column(String(32), nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)

    status: Mapped[BenefitGrantStatus] = mapped_column(enum_type(BenefitGrantStatus, 16), nullable=False)
    requested_quantity: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    granted_quantity: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)

    result: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    started_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    meta: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)

    subscription_benefit: Mapped[SubscriptionBenefit] = relationship(SubscriptionBenefit)
