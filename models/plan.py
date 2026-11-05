from decimal import Decimal

from sqlalchemy import JSON, Boolean, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from enums.benefit_policy import BenefitPolicy
from enums.interval_unit import IntervalUnit
from enums.resume_delivery_policy import ResumeDeliveryPolicy
from helpers.database_base import Base
from helpers.search import search_index
from models.addressed_mixin import AddressedMixin
from models.base import Money, enum_type, language_scoped_unique
from models.identified_mixin import BigId, IdentifiedMixin
from models.language import Language
from models.tenant import Tenant
from models.timestamp_mixin import TimestampMixin


class Plan(Base, IdentifiedMixin, AddressedMixin, TimestampMixin):
    """A recurring offering of exactly one tenant, priced here only so the site can show it."""

    __tablename__ = "subscription_plan"
    __table_args__ = (UniqueConstraint("uuid", name="subscription_plan_uuid"), language_scoped_unique("subscription_plan_tenant_code", "code"), Index("subscription_plan_order", "tenant_id", "position"), search_index("subscription_plan_search", "name"))

    tenant_id: Mapped[int | None] = mapped_column(BigId, ForeignKey("tenant.id", ondelete="CASCADE"), nullable=True)

    # The same plan is sold once per market, so a price is written in the currency of the language it is read in.
    language_id: Mapped[int | None] = mapped_column(BigId, ForeignKey("language.id", ondelete="RESTRICT"), nullable=True)

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    image: Mapped[str | None] = mapped_column(String(512), nullable=True)

    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    price: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"), nullable=False)

    billing_interval_unit: Mapped[IntervalUnit | None] = mapped_column(enum_type(IntervalUnit, 16), nullable=True)
    billing_interval_value: Mapped[int | None] = mapped_column(Integer, nullable=True)

    resume_delivery_policy: Mapped[ResumeDeliveryPolicy] = mapped_column(enum_type(ResumeDeliveryPolicy), default=ResumeDeliveryPolicy.SAME_CYCLE, nullable=False)
    trial_benefit_policy: Mapped[BenefitPolicy] = mapped_column(enum_type(BenefitPolicy), default=BenefitPolicy.ACCESS_ONLY, nullable=False)
    grace_benefit_policy: Mapped[BenefitPolicy] = mapped_column(enum_type(BenefitPolicy), default=BenefitPolicy.ACCESS_ONLY, nullable=False)

    featured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    meta: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)

    tenant: Mapped[Tenant] = relationship(Tenant)
    language: Mapped[Language | None] = relationship(Language)
