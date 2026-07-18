from typing import Protocol

from fastkit_mail.provider.health import ProviderHealth
from fastkit_mail.provider.message import EmailMessage
from fastkit_mail.provider.result import EmailProviderResult


class EmailProvider(Protocol):
    async def send(self, message: EmailMessage) -> EmailProviderResult: ...

    async def health(self) -> ProviderHealth: ...
