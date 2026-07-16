import json
import uuid

from sqlalchemy import CHAR, Text
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


class PortableJSON(TypeDecorator):
    """JSON stored as text so behaviour is identical on SQLite, PostgreSQL and MySQL."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None

        return json.dumps(value, separators=(",", ":"), sort_keys=True)

    def process_result_value(self, value, dialect):
        if value is None:
            return None

        return json.loads(value)


def new_uuid() -> uuid.UUID:
    return uuid.uuid4()
