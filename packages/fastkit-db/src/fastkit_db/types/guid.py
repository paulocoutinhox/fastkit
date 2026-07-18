import uuid

from sqlalchemy import CHAR
from sqlalchemy.types import TypeDecorator


class GUID(TypeDecorator):
    """Portable UUID stored as a 32 character hex string across every supported dialect."""

    impl = CHAR(32)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None

        if isinstance(value, uuid.UUID):
            return value.hex

        return uuid.UUID(str(value)).hex

    def process_result_value(self, value, dialect):
        if value is None:
            return None

        return uuid.UUID(value)
