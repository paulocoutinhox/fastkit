from fastkit_mail.provider import EmailMessage, EmailProviderResult, ProviderHealth, ProviderStatus


class MemoryEmailProvider:
    """Collects messages in memory for local development and tests."""

    def __init__(self, fail: bool = False):
        self.sent: list[EmailMessage] = []
        self.fail = fail
        self._counter = 0

    async def send(self, message: EmailMessage) -> EmailProviderResult:
        if self.fail:
            return EmailProviderResult(success=False, error="memory provider forced failure")

        self._counter += 1
        self.sent.append(message)

        return EmailProviderResult(success=True, message_id=f"mem-{self._counter}")

    async def health(self) -> ProviderHealth:
        if self.fail:
            return ProviderHealth(ProviderStatus.unavailable, detail="forced failure")

        return ProviderHealth(ProviderStatus.healthy)
