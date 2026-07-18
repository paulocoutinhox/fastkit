from dataclasses import dataclass


@dataclass(frozen=True)
class ObjectStat:
    key: str
    size_bytes: int
    content_type: str | None
