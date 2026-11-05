from datetime import datetime

from sqlalchemy import JSON, Boolean, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from enums.benefit_status import BenefitStatus
from enums.environment import Environment
from enums.subscription import ELIGIBLE_SUBSCRIPTION_STATUSES
from enums.subscription_status import SubscriptionStatus
from helpers.database_base import Base
from models.base import enum_type
from models.identified_mixin import BigId, IdentifiedMixin
from models.plan import Plan
from models.tenant import Tenant
from models.timestamp_mixin import TimestampMixin
from models.user import User
from models.utc_date_time import UtcDateTime


class Subscription(Base, IdentifiedMixin, TimestampMixin):
    __tablename__ = "subscription"
    __table_args__ = (
        UniqueConstraint("integration_id", "external_id", name="subscription_integration_external"),
        UniqueConstraint("user_id", "integration_id", "external_product_id", name="subscription_account_product"),
        Index("subscription_user_status", "user_id", "status"),
        Index("subscription_status_access", "status", "benefit_status", "access_until"),
        Index("subscription_tenant", "tenant_id", "status"),
    )

    tenant_id: Mapped[int | None] = mapped_column(BigId, ForeignKey("tenant.id", ondelete="CASCADE"), nullable=True)
    user_id: Mapped[int] = mapped_column(BigId, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    plan_id: Mapped[int] = mapped_column(BigId, ForeignKey("subscription_plan.id", ondelete="RESTRICT"), nullable=False)
    integration_id: Mapped[int | None] = mapped_column(BigId, ForeignKey("integration.id", ondelete="RESTRICT"), nullable=True)
    external_product_id: Mapped[int | None] = mapped_column(BigId, ForeignKey("integration_external_product.id", ondelete="RESTRICT"), nullable=True)

    external_id: Mapped[str | None] = mapped_column(String(191), nullable=True)

    status: Mapped[SubscriptionStatus] = mapped_column(enum_type(SubscriptionStatus), default=SubscriptionStatus.PENDING, nullable=False)
    benefit_status: Mapped[BenefitStatus] = mapped_column(enum_type(BenefitStatus, 16), default=BenefitStatus.ACTIVE, nullable=False)
    environment: Mapped[Environment | None] = mapped_column(enum_type(Environment, 16), nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    current_period_started_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    current_period_ends_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    access_until: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    trial_ends_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    grace_until: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)

    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    canceled_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)
    expired_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)

    # When the gateway said what this row carries, because it delivers out of order and replays what failed, and an older word never moves a newer one.
    stated_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)

    meta: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)

    tenant: Mapped[Tenant] = relationship(Tenant)
    user: Mapped[User] = relationship(User)
    plan: Mapped[Plan] = relationship(Plan)

    @property
    def is_eligible_for_benefits(self) -> bool:
        return self.status in ELIGIBLE_SUBSCRIPTION_STATUSES and self.benefit_status == BenefitStatus.ACTIVE
