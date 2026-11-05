from datetime import datetime

from sqlalchemy import JSON, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from helpers.database_base import Base
from helpers.dates import now
from models.identified_mixin import BigId, IdentifiedMixin
from models.product import Product
from models.timestamp_mixin import TimestampMixin
from models.user import User
from models.utc_date_time import UtcDateTime


class UserProduct(Base, IdentifiedMixin, TimestampMixin):
    """What the account owns for good, however it got there, because nothing here ever takes one back."""

    __tablename__ = "user_product"
    __table_args__ = (UniqueConstraint("user_id", "product_id", name="user_product_unique"), Index("user_product_owned", "user_id", "granted_at"))

    user_id: Mapped[int] = mapped_column(BigId, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[int] = mapped_column(BigId, ForeignKey("commerce_product.id", ondelete="RESTRICT"), nullable=False)
    purchase_id: Mapped[int | None] = mapped_column(BigId, ForeignKey("commerce_purchase.id", ondelete="SET NULL"), nullable=True)
    subscription_id: Mapped[int | None] = mapped_column(BigId, ForeignKey("subscription.id", ondelete="SET NULL"), nullable=True)
    benefit_grant_id: Mapped[int | None] = mapped_column(BigId, ForeignKey("subscription_benefit_grant.id", ondelete="SET NULL"), nullable=True)

    granted_at: Mapped[datetime] = mapped_column(UtcDateTime, default=now, nullable=False)
    meta: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)

    user: Mapped[User] = relationship(User)
    product: Mapped[Product] = relationship(Product)
