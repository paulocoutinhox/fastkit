from typing import Protocol

from fastkit_webhooks.provider.normalized import NormalizedWebhook
from fastkit_webhooks.provider.request import RawWebhookRequest
from fastkit_webhooks.provider.verification import VerificationResult


class WebhookProvider(Protocol):
    name: str

    async def verify(self, request: RawWebhookRequest) -> VerificationResult: ...

    async def normalize(self, request: RawWebhookRequest) -> NormalizedWebhook: ...
