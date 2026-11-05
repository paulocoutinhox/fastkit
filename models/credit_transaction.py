from sqlalchemy import JSON, BigInteger, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from enums.credit_transaction_type import CreditTransactionType
from helpers.database_base import Base
from helpers.search import search_index
from models.base import enum_type
from models.currency import Currency
from models.identified_mixin import BigId, IdentifiedMixin
from models.timestamp_mixin import TimestampMixin
from models.user import User


class CreditTransaction(Base, IdentifiedMixin, TimestampMixin):
    """The ledger of one currency, where `idempotency_key` keeps a replayed delivery from crediting twice."""

    __tablename__ = "credit_transaction"
    __table_args__ = (UniqueConstraint("idempotency_key", name="credit_transaction_idempotency_key"), Index("credit_transaction_holder", "user_id", "currency_id", "created_at"), search_index("credit_transaction_search", "description"))

    user_id: Mapped[int] = mapped_column(BigId, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    currency_id: Mapped[int] = mapped_column(BigId, ForeignKey("currency.id", ondelete="RESTRICT"), nullable=False)
    benefit_grant_id: Mapped[int | None] = mapped_column(BigId, ForeignKey("subscription_benefit_grant.id", ondelete="SET NULL"), nullable=True)

    type: Mapped[CreditTransactionType] = mapped_column(enum_type(CreditTransactionType, 16), nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    balance_after: Mapped[int] = mapped_column(BigInteger, nullable=False)

    idempotency_key: Mapped[str] = mapped_column(String(191), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    meta: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)

    user: Mapped[User] = relationship(User)
    currency: Mapped[Currency] = relationship(Currency)
