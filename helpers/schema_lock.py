"""A lock held while the schema is built, where the statement that takes it answers 1 once it is taken."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SchemaLock:
    take: str

    # What gives a lock of the session back, and nothing where the lock belongs to the transaction and ends with it.
    release: str | None = None

    # What bounds the wait for a lock whose statement waits forever, said before it is taken.
    bound: str | None = None
