from dataclasses import dataclass


@dataclass(frozen=True)
class RecaptchaConfig:
    action: str
    minimum_score: float
    allowed_hostnames: tuple[str, ...]
