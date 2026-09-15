from datetime import datetime
from uuid import uuid4

from sqlalchemy import BigInteger, DateTime, Index, Integer, Numeric, String, TypeDecorator, func
from sqlalchemy import Enum as SqlEnum
from sqlalchemy import column as sql_column
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column

from helpers.dates import as_utc, naive_utc, now

# What each width holds, which is the ceiling on every number a caller types: one past it overflows inside the driver and answers a five hundred where a refusal was meant.
BIG_INTEGER_MAX = 9223372036854775807

INTEGER_MAX = 2147483647

BigId = BigInteger().with_variant(Integer, "sqlite")

# What an amount of money is kept as, where three is what the smallest unit of a dinar needs and two would silently round what a gateway reported.
Money = Numeric(12, 3)


def enum_type(enum_class, length: int = 32) -> SqlEnum:
    return SqlEnum(enum_class, native_enum=False, length=length, values_callable=lambda members: [member.value for member in members])


class UtcDateTime(TypeDecorator):
    """Timestamps live in the database as naive UTC and reach the application as aware UTC."""

    impl = DateTime
    cache_ok = True

    def load_dialect_impl(self, dialect):
        """MySQL keeps whole seconds unless the column asks for the fraction, and a timestamp that lost it stops equalling the one that is still in memory."""
        if dialect.name == "mysql":
            return dialect.type_descriptor(mysql.DATETIME(fsp=6))

        return dialect.type_descriptor(DateTime())

    def process_bind_param(self, value, dialect):
        return naive_utc(value)

    def process_result_value(self, value, dialect):
        return as_utc(value)


class IdentifiedMixin:
    id: Mapped[int] = mapped_column(BigId, primary_key=True, autoincrement=True)


class AddressedMixin:
    """The name a record answers by outside this application, because an autoincrement id is guessable and says how many of them exist."""

    uuid: Mapped[str] = mapped_column(String(36), default=lambda: str(uuid4()), nullable=False)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, default=now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, default=now, onupdate=now, nullable=False)


def tenant_scoped_unique(name: str, column: str) -> Index:
    """Unique inside the tenant, where the rows with no tenant are a scope of their own — a plain unique index lets those through, because no null equals another."""
    return Index(name, func.coalesce(sql_column("tenant_id"), 0), column, unique=True)


def language_scoped_unique(name: str, column: str) -> Index:
    """Unique inside the tenant and the language both, where a row naming neither sits in a scope of its own for the same reason."""
    return Index(name, func.coalesce(sql_column("tenant_id"), 0), column, func.coalesce(sql_column("language_id"), 0), unique=True)
