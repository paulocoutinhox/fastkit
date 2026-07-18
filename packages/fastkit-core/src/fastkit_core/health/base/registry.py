from typing import Awaitable, Callable

from fastkit_core.health.base.report import HealthReport
from fastkit_core.health.base.result import HealthResult
from fastkit_core.health.base.status import HealthStatus

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
