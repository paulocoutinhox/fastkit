import json
from dataclasses import dataclass, field
from typing import Protocol

from fastkit_webhooks.signature import verify_signature


@dataclass(frozen=True)
class RawWebhookRequest:
    headers: dict
    body: bytes


@dataclass(frozen=True)
class VerificationResult:
    valid: bool
    reason: str | None = None


@dataclass(frozen=True)
class NormalizedWebhook:
    provider_account_id: str
    external_event_id: str
    event_type: str
    payload: dict = field(default_factory=dict)


class WebhookProvider(Protocol):
    name: str

    async def verify(self, request: RawWebhookRequest) -> VerificationResult:
        ...

    async def normalize(self, request: RawWebhookRequest) -> NormalizedWebhook:
        ...


class HmacWebhookProvider:
    """Generic provider verifying an HMAC signature header over the raw body."""

    def __init__(self, name: str, secret: str, signature_header: str = "x-signature"):
        self.name = name
        self._secret = secret
        self._signature_header = signature_header.lower()

    async def verify(self, request: RawWebhookRequest) -> VerificationResult:
        provided = {key.lower(): value for key, value in request.headers.items()}.get(self._signature_header)

        if verify_signature(self._secret, request.body, provided):
            return VerificationResult(valid=True)

        return VerificationResult(valid=False, reason="invalid signature")

    async def normalize(self, request: RawWebhookRequest) -> NormalizedWebhook:
        payload = json.loads(request.body.decode("utf-8"))

        if not isinstance(payload, dict):
            raise ValueError("webhook payload must be a JSON object")

        return NormalizedWebhook(
            provider_account_id=str(payload.get("account_id", "default")),
            external_event_id=str(payload["id"]),
            event_type=str(payload.get("type", "unknown")),
            payload=payload,
        )
