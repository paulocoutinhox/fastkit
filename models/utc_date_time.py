from sqlalchemy import DateTime, TypeDecorator
from sqlalchemy.dialects import mysql

from helpers.dates import as_utc, naive_utc


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
