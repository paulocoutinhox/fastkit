from dataclasses import dataclass, field

from fastkit_core.health.base.result import HealthResult
from fastkit_core.health.base.status import HealthStatus


@dataclass
class HealthReport:
    checks: list[HealthResult] = field(default_factory=list)

    @property
    def status(self) -> HealthStatus:
        statuses = {check.status for check in self.checks}

        if HealthStatus.unavailable in statuses:
            return HealthStatus.unavailable

        if HealthStatus.degraded in statuses:
            return HealthStatus.degraded

        return HealthStatus.healthy

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "checks": [
                {
                    "name": check.name,
                    "status": check.status.value,
                    "detail": check.detail,
                }
                for check in self.checks
            ],
        }
