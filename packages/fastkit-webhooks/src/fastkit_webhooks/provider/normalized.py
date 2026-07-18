from dataclasses import dataclass, field


@dataclass(frozen=True)
class NormalizedWebhook:
    provider_account_id: str
    external_event_id: str
    event_type: str
    payload: dict = field(default_factory=dict)
