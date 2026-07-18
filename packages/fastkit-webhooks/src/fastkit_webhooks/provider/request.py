from dataclasses import dataclass


@dataclass(frozen=True)
class RawWebhookRequest:
    headers: dict
    body: bytes
