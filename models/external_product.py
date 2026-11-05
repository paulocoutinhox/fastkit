from decimal import Decimal

from sqlalchemy import JSON, Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from helpers.database_base import Base
from helpers.search import search_index
from models.base import Money
from models.identified_mixin import BigId, IdentifiedMixin
from models.integration import Integration
from models.plan import Plan
from models.timestamp_mixin import TimestampMixin


class ExternalProduct(Base, IdentifiedMixin, TimestampMixin):
    """What a plan is sold as inside one provider, where the price is a reference and not what a buyer pays."""

    __tablename__ = "integration_external_product"
    __table_args__ = (UniqueConstraint("integration_id", "external_id", name="integration_external_product_ext"), search_index("integration_external_product_search", "display_name"))

    integration_id: Mapped[int] = mapped_column(BigId, ForeignKey("integration.id", ondelete="CASCADE"), nullable=False)
    plan_id: Mapped[int] = mapped_column(BigId, ForeignKey("subscription_plan.id", ondelete="RESTRICT"), nullable=False)

    external_id: Mapped[str] = mapped_column(String(191), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reference_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    reference_price: Mapped[Decimal | None] = mapped_column(Money, nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    meta: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)

    integration: Mapped[Integration] = relationship(Integration)
    plan: Mapped[Plan] = relationship(Plan)
