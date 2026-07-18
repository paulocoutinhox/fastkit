from dataclasses import dataclass, field
from enum import Enum
from typing import Awaitable, Callable


class HealthStatus(str, Enum):
    healthy = "healthy"
    degraded = "degraded"
    unavailable = "unavailable"


@dataclass(frozen=True)
class HealthResult:
    name: str
    status: HealthStatus
    detail: str | None = None


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


HealthCheck = Callable[[], Awaitable[HealthResult]]


class HealthCheckRegistry:
    def __init__(self):
        self._checks: dict[str, HealthCheck] = {}

    def register(self, name: str, check: HealthCheck) -> None:
        self._checks[name] = check

    async def run(self) -> HealthReport:
        report = HealthReport()

        for name, check in self._checks.items():
            report.checks.append(await self._run_check(name, check))

        return report

    async def _run_check(self, name: str, check: HealthCheck) -> HealthResult:
        try:
            return await check()
        except Exception as error:
            return HealthResult(
                name=name, status=HealthStatus.unavailable, detail=str(error)
            )
