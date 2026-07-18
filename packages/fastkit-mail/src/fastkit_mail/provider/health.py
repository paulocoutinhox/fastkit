from dataclasses import dataclass

from fastkit_mail.provider.status import ProviderStatus


@dataclass(frozen=True)
class ProviderHealth:
    status: ProviderStatus
    detail: str | None = None
