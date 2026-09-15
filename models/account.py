from sqlalchemy import JSON, BigInteger, Boolean, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from enums.account import CreditTransactionType
from helpers.db import Base
from helpers.search import search_index
from models.base import AddressedMixin, BigId, IdentifiedMixin, TimestampMixin, enum_type, tenant_scoped_unique
from models.tenant import Tenant
from models.user import User


class Currency(Base, IdentifiedMixin, AddressedMixin, TimestampMixin):
    """A unit an account holds a balance in, which is whatever the product decides to call it and never a fixed pair."""

    __tablename__ = "currency"
    __table_args__ = (UniqueConstraint("uuid", name="currency_uuid"), tenant_scoped_unique("currency_code", "code"), Index("currency_listing", "tenant_id", "active", "position"), search_index("currency_search", "name"))

    tenant_id: Mapped[int | None] = mapped_column(BigId, ForeignKey("tenant.id", ondelete="CASCADE"), nullable=True)

    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    symbol: Mapped[str | None] = mapped_column(String(8), nullable=True)

    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    meta: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)

    tenant: Mapped[Tenant | None] = relationship(Tenant)


class UserBalance(Base, IdentifiedMixin, TimestampMixin):
    """What one account holds of one currency, which is the running total the ledger of that currency explains."""

    __tablename__ = "user_balance"
    __table_args__ = (UniqueConstraint("user_id", "currency_id", name="user_balance_unique"),)

    user_id: Mapped[int] = mapped_column(BigId, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    currency_id: Mapped[int] = mapped_column(BigId, ForeignKey("currency.id", ondelete="RESTRICT"), nullable=False)

    amount: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)

    user: Mapped[User] = relationship(User)
    currency: Mapped[Currency] = relationship(Currency)


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
