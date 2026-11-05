from enum import StrEnum


class Naming(StrEnum):
    """What a stored file is called, where the uuid is always in the key so the orphan sweep can still find it."""

    UUID = "uuid"
    ORIGINAL = "original"
