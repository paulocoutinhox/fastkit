from dataclasses import dataclass


@dataclass(frozen=True)
class ProcessedVariant:
    data: bytes
    format: str
    mime_type: str
    width: int
    height: int
    size_bytes: int
