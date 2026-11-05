from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from enums.benefit_cadence import BenefitCadence
from enums.benefit_status import BenefitStatus
from enums.benefit_type import BenefitType
from enums.interval_unit import IntervalUnit
from enums.missed_cycle_policy import MissedCyclePolicy
from helpers.database_base import Base
from models.base import enum_type
from models.benefit import Benefit
from models.currency import Currency
from models.identified_mixin import BigId, IdentifiedMixin
from models.product import Product
from models.subscription import Subscription
from models.timestamp_mixin import TimestampMixin
from models.utc_date_time import UtcDateTime


class SubscriptionBenefit(Base, IdentifiedMixin, TimestampMixin):
    """The snapshot of a benefit taken when the subscription activated, so editing the catalog later never rewrites what a live subscription promised."""

    __tablename__ = "subscription_benefit"
    __table_args__ = (UniqueConstraint("subscription_id", "benefit_id", name="subscription_benefit_unique"), Index("subscription_benefit_due", "status", "next_grant_at"))

    subscription_id: Mapped[int] = mapped_column(BigId, ForeignKey("subscription.id", ondelete="CASCADE"), nullable=False)
    benefit_id: Mapped[int] = mapped_column(BigId, ForeignKey("subscription_benefit_catalog.id", ondelete="RESTRICT"), nullable=False)
    user_entitlement_id: Mapped[int] = mapped_column(BigId, ForeignKey("subscription_user_entitlement.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[int | None] = mapped_column(BigId, ForeignKey("commerce_product.id", ondelete="RESTRICT"), nullable=True)
    currency_id: Mapped[int | None] = mapped_column(BigId, ForeignKey("currency.id", ondelete="RESTRICT"), nullable=True)

    status: Mapped[BenefitStatus] = mapped_column(enum_type(BenefitStatus, 16), default=BenefitStatus.ACTIVE, nullable=False)
    benefit_type: Mapped[BenefitType] = mapped_column(enum_type(BenefitType), nullable=False)
    target: Mapped[str] = mapped_column(String(191), nullable=False)
    quantity: Mapped[int] = mapped_column(BigInteger, nullable=False)

    cadence: Mapped[BenefitCadence] = mapped_column(enum_type(BenefitCadence), nullable=False)
    interval_unit: Mapped[IntervalUnit | None] = mapped_column(enum_type(IntervalUnit, 16), nullable=True)
    interval_value: Mapped[int | None] = mapped_column(Integer, nullable=True)

    grant_on_activation: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    missed_cycle_policy: Mapped[MissedCyclePolicy] = mapped_column(enum_type(MissedCyclePolicy), default=MissedCyclePolicy.SKIP, nullable=False)

    anchor_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False)
    cycle: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_grant_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    next_grant_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    meta: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)

    subscription: Mapped[Subscription] = relationship(Subscription)
    benefit: Mapped[Benefit] = relationship(Benefit)
    product: Mapped[Product | None] = relationship(Product)
    currency: Mapped[Currency | None] = relationship(Currency)
