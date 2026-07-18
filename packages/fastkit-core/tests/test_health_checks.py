import pytest

from fastkit_core.checks.base import (
    CheckLevel,
    CheckMessage,
    SystemCheckError,
    SystemCheckRegistry,
)
from fastkit_core.health.base import HealthCheckRegistry, HealthResult, HealthStatus


async def test_health_report_aggregates_worst_status():
    registry = HealthCheckRegistry()

    async def healthy():
        return HealthResult("db", HealthStatus.healthy)

    async def degraded():
        return HealthResult("cache", HealthStatus.degraded, detail="reconnecting")

    registry.register("db", healthy)
    registry.register("cache", degraded)

    report = await registry.run()

    assert report.status is HealthStatus.degraded
    assert report.to_dict()["status"] == "degraded"
    assert len(report.to_dict()["checks"]) == 2


async def test_health_report_unavailable_wins():
    registry = HealthCheckRegistry()

    async def down():
        return HealthResult("db", HealthStatus.unavailable)

    async def degraded():
        return HealthResult("cache", HealthStatus.degraded)

    registry.register("db", down)
    registry.register("cache", degraded)

    assert (await registry.run()).status is HealthStatus.unavailable


async def test_empty_health_report_is_healthy():
    assert (await HealthCheckRegistry().run()).status is HealthStatus.healthy


async def test_a_raising_check_reports_unavailable_instead_of_crashing():
    registry = HealthCheckRegistry()

    async def broken():
        raise RuntimeError("connection refused")

    registry.register("db", broken)

    report = await registry.run()

    assert report.status is HealthStatus.unavailable
    assert report.checks[0].name == "db"
    assert report.checks[0].detail == "connection refused"


def test_system_checks_collect_messages():
    registry = SystemCheckRegistry()
    registry.register("info", lambda: [CheckMessage(CheckLevel.info, "ok")])
    registry.register("warn", lambda: [CheckMessage(CheckLevel.warning, "careful")])

    messages = registry.run()

    assert len(messages) == 2
    assert registry.run_or_raise() == messages


def test_system_checks_raise_on_error():
    registry = SystemCheckRegistry()
    registry.register(
        "bad", lambda: [CheckMessage(CheckLevel.error, "broken", hint="fix it")]
    )

    with pytest.raises(SystemCheckError, match="broken"):
        registry.run_or_raise()
