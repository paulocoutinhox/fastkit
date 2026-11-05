from sqlalchemy import Enum as SqlEnum
from sqlalchemy import Index, Numeric, func
from sqlalchemy import column as sql_column

# What each width holds, which is the ceiling on every number a caller types: one past it overflows inside the driver and answers a five hundred where a refusal was meant.
BIG_INTEGER_MAX = 9223372036854775807


INTEGER_MAX = 2147483647


# MySQL stores a JSON document at most a hundred levels deep, and a map far short of that is already more than anything here writes.
JSON_DEPTH_MAX = 32


# What an amount of money is kept as, where three is what the smallest unit of a dinar needs and two would silently round what a gateway reported.
Money = Numeric(12, 3)


def enum_type(enum_class, length: int = 32) -> SqlEnum:
    return SqlEnum(enum_class, native_enum=False, length=length, values_callable=lambda members: [member.value for member in members])


def tenant_scoped_unique(name: str, column: str) -> Index:
    """Unique inside the tenant, where the rows with no tenant are a scope of their own — a plain unique index lets those through, because no null equals another."""
    return Index(name, func.coalesce(sql_column("tenant_id"), 0), column, unique=True)


def language_scoped_unique(name: str, column: str) -> Index:
    """Unique inside the tenant and the language both, where a row naming neither sits in a scope of its own for the same reason."""
    return Index(name, func.coalesce(sql_column("tenant_id"), 0), column, func.coalesce(sql_column("language_id"), 0), unique=True)
