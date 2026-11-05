from sqlalchemy import JSON, BigInteger, Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from enums.benefit_cadence import BenefitCadence
from enums.benefit_type import BenefitType
from enums.interval_unit import IntervalUnit
from enums.missed_cycle_policy import MissedCyclePolicy
from helpers.database_base import Base
from models.base import enum_type
from models.currency import Currency
from models.entitlement import Entitlement
from models.identified_mixin import BigId, IdentifiedMixin
from models.product import Product
from models.timestamp_mixin import TimestampMixin


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
