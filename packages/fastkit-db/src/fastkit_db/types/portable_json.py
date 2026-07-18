import json

from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator


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
