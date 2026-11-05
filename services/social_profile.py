from dataclasses import dataclass


@dataclass(frozen=True)
class SocialProfile:
    subject: str
    email: str | None = None
