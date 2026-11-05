from sqlalchemy import BigInteger, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from helpers.database_base import Base
from models.currency import Currency
from models.identified_mixin import BigId, IdentifiedMixin
from models.timestamp_mixin import TimestampMixin
from models.user import User


class UserBalance(Base, IdentifiedMixin, TimestampMixin):
    """What one account holds of one currency, which is the running total the ledger of that currency explains."""

    __tablename__ = "user_balance"
    __table_args__ = (UniqueConstraint("user_id", "currency_id", name="user_balance_unique"),)

    user_id: Mapped[int] = mapped_column(BigId, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    currency_id: Mapped[int] = mapped_column(BigId, ForeignKey("currency.id", ondelete="RESTRICT"), nullable=False)

    amount: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)

    user: Mapped[User] = relationship(User)
    currency: Mapped[Currency] = relationship(Currency)
