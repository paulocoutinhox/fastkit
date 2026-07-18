from dataclasses import dataclass

from fastkit_core.health.base.status import HealthStatus


@dataclass(frozen=True)
class HealthResult:
    name: str
    status: HealthStatus
    detail: str | None = None
