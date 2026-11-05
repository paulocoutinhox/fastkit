"""A lock of the session, held while the schema is built, where each statement answers 1 once it is taken."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SchemaLock:
    take: str
    release: str
