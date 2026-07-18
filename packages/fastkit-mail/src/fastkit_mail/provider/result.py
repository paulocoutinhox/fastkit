from dataclasses import dataclass


@dataclass(frozen=True)
class EmailProviderResult:
    success: bool
    message_id: str | None = None
    error: str | None = None
