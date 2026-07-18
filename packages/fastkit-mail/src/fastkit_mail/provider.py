from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol


class ProviderStatus(str, Enum):
    healthy = "healthy"
    unavailable = "unavailable"


@dataclass(frozen=True)
class ProviderHealth:
    status: ProviderStatus
    detail: str | None = None


@dataclass
class EmailMessage:
    to: list[str]
    subject: str
    html_body: str
    text_body: str
    from_email: str
    cc: list[str] = field(default_factory=list)
    bcc: list[str] = field(default_factory=list)
    reply_to: str | None = None


@dataclass(frozen=True)
class EmailProviderResult:
    success: bool
    message_id: str | None = None
    error: str | None = None


class EmailProvider(Protocol):
    async def send(self, message: EmailMessage) -> EmailProviderResult: ...

    async def health(self) -> ProviderHealth: ...
