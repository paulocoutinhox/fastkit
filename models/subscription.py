from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, BigInteger, Boolean, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from enums.integration import Environment
from enums.subscription import ELIGIBLE_SUBSCRIPTION_STATUSES, BenefitCadence, BenefitGrantStatus, BenefitPolicy, BenefitStatus, BenefitType, IntervalUnit, MissedCyclePolicy, ResumeDeliveryPolicy, SubscriptionStatus, UserEntitlementStatus
from helpers.db import Base
from helpers.search import search_index
from models.account import Currency
from models.base import AddressedMixin, BigId, IdentifiedMixin, Money, TimestampMixin, UtcDateTime, enum_type, language_scoped_unique, tenant_scoped_unique
from models.commerce import Product
from models.language import Language
from models.tenant import Tenant
from models.user import User


class Entitlement(Base, IdentifiedMixin, TimestampMixin):
    __tablename__ = "subscription_entitlement"
    __table_args__ = (tenant_scoped_unique("subscription_entitlement_tenant_code", "code"), Index("subscription_entitlement_order", "tenant_id", "name"), search_index("subscription_entitlement_search", "name"))

    tenant_id: Mapped[int | None] = mapped_column(BigId, ForeignKey("tenant.id", ondelete="CASCADE"), nullable=True)

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    meta: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)

    tenant: Mapped[Tenant | None] = relationship(Tenant)


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


class PlanEntitlement(Base, IdentifiedMixin, TimestampMixin):
    __tablename__ = "subscription_plan_entitlement"
    __table_args__ = (UniqueConstraint("plan_id", "entitlement_id", name="subscription_plan_entitlement_unique"),)

    plan_id: Mapped[int] = mapped_column(BigId, ForeignKey("subscription_plan.id", ondelete="CASCADE"), nullable=False)
    entitlement_id: Mapped[int] = mapped_column(BigId, ForeignKey("subscription_entitlement.id", ondelete="CASCADE"), nullable=False)

    meta: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)

    plan: Mapped[Plan] = relationship(Plan)
    entitlement: Mapped[Entitlement] = relationship(Entitlement)


class Benefit(Base, IdentifiedMixin, TimestampMixin):
    __tablename__ = "subscription_benefit_catalog"
    __table_args__ = (UniqueConstraint("entitlement_id", "target", name="subscription_benefit_catalog_target"),)

    entitlement_id: Mapped[int] = mapped_column(BigId, ForeignKey("subscription_entitlement.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[int | None] = mapped_column(BigId, ForeignKey("commerce_product.id", ondelete="RESTRICT"), nullable=True)
    currency_id: Mapped[int | None] = mapped_column(BigId, ForeignKey("currency.id", ondelete="RESTRICT"), nullable=True)

    type: Mapped[BenefitType] = mapped_column(enum_type(BenefitType), nullable=False)
    target: Mapped[str] = mapped_column(String(191), nullable=False)
    quantity: Mapped[int] = mapped_column(BigInteger, default=1, nullable=False)

    cadence: Mapped[BenefitCadence] = mapped_column(enum_type(BenefitCadence), nullable=False)
    interval_unit: Mapped[IntervalUnit | None] = mapped_column(enum_type(IntervalUnit, 16), nullable=True)
    interval_value: Mapped[int | None] = mapped_column(Integer, nullable=True)

    grant_on_activation: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    missed_cycle_policy: Mapped[MissedCyclePolicy] = mapped_column(enum_type(MissedCyclePolicy), default=MissedCyclePolicy.SKIP, nullable=False)

    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    meta: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)

    entitlement: Mapped[Entitlement] = relationship(Entitlement)
    product: Mapped[Product | None] = relationship(Product)
    currency: Mapped[Currency | None] = relationship(Currency)


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

    meta: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)

    tenant: Mapped[Tenant] = relationship(Tenant)
    user: Mapped[User] = relationship(User)
    plan: Mapped[Plan] = relationship(Plan)

    @property
    def is_eligible_for_benefits(self) -> bool:
        return self.status in ELIGIBLE_SUBSCRIPTION_STATUSES and self.benefit_status == BenefitStatus.ACTIVE


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


class BenefitGrant(Base, IdentifiedMixin, TimestampMixin):
    """One delivery attempt of one cycle, made idempotent by `grant_key` so a replay never hands the same thing out twice."""

    __tablename__ = "subscription_benefit_grant"
    __table_args__ = (UniqueConstraint("grant_key", name="subscription_benefit_grant_key"), UniqueConstraint("subscription_benefit_id", "cycle_key", name="subscription_benefit_grant_cycle"), Index("subscription_benefit_grant_status", "status", "created_at"))

    subscription_benefit_id: Mapped[int] = mapped_column(BigId, ForeignKey("subscription_benefit.id", ondelete="CASCADE"), nullable=False)

    grant_key: Mapped[str] = mapped_column(String(191), nullable=False)
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
