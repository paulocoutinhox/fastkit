from dataclasses import dataclass


@dataclass(frozen=True)
class PresignedUrl:
    url: str
    method: str
    expires_in: int
