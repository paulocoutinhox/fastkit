from sqlalchemy import JSON, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from helpers.database_base import Base
from models.entitlement import Entitlement
from models.identified_mixin import BigId, IdentifiedMixin
from models.plan import Plan
from models.timestamp_mixin import TimestampMixin


class PlanEntitlement(Base, IdentifiedMixin, TimestampMixin):
    __tablename__ = "subscription_plan_entitlement"
    __table_args__ = (UniqueConstraint("plan_id", "entitlement_id", name="subscription_plan_entitlement_unique"),)

    plan_id: Mapped[int] = mapped_column(BigId, ForeignKey("subscription_plan.id", ondelete="CASCADE"), nullable=False)
    entitlement_id: Mapped[int] = mapped_column(BigId, ForeignKey("subscription_entitlement.id", ondelete="CASCADE"), nullable=False)

    meta: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)

    plan: Mapped[Plan] = relationship(Plan)
    entitlement: Mapped[Entitlement] = relationship(Entitlement)
