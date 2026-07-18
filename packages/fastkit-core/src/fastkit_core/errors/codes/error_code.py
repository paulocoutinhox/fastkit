from dataclasses import dataclass

from fastkit_core.errors.codes.severity import Severity


@dataclass(frozen=True)
class ErrorCode:
    code: str
    http_status: int
    translation_key: str
    severity: Severity = Severity.error
    retryable: bool = False
    should_log: bool = True
    user_visible: bool = True
