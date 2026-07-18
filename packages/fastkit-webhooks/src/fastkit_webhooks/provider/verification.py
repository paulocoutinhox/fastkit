from dataclasses import dataclass


@dataclass(frozen=True)
class VerificationResult:
    valid: bool
    reason: str | None = None
