import pytest

from fastkit_cli import commands
from fastkit_cli.cli import build_parser, run
from fastkit_cli.entry import main


async def test_apps_list(runtime):
    _, lines = await run(runtime, ["apps", "list"])

    assert any("fastkit.core" in line for line in lines)


async def test_apps_graph(runtime):
    _, lines = await run(runtime, ["apps", "graph"])

    assert any("fastkit.accounts <-" in line for line in lines)


async def test_checks(runtime):
    _, lines = await run(runtime, ["checks"])

    assert lines == ["all system checks passed"]


async def test_routes_empty(runtime):
    _, lines = await run(runtime, ["routes"])

    assert lines == ["no routers registered"]


async def test_health(runtime):
    _, lines = await run(runtime, ["health"])

    assert any("database" in line for line in lines)


async def test_db_bootstrap(runtime):
    _, lines = await run(runtime, ["db", "bootstrap"])

    assert lines == ["seeded 3 language(s)"]


async def test_create_root(runtime):
    _, lines = await run(
        runtime,
        [
            "admin",
            "create-root",
            "--email",
            "root@platform.com",
            "--password",
            "supersecret-123",
        ],
    )

    assert "created root user root@platform.com" in lines[0]


async def test_db_bootstrap_without_content():
    from fastkit_core.runtime import Runtime

    class Settings:
        installed_apps = []

    runtime = Runtime(settings=Settings(), installed_apps=[])
    lines = await commands.db_bootstrap(runtime)

    assert lines == ["content app is not installed, nothing to seed"]


async def test_checks_with_messages():
    from fastkit_core.checks.base import CheckLevel, CheckMessage
    from fastkit_core.runtime import Runtime

    class Settings:
        installed_apps = []

    runtime = Runtime(settings=Settings(), installed_apps=[])
    runtime.checks.register(
        "demo", lambda: [CheckMessage(CheckLevel.warning, "careful")]
    )

    lines = await commands.run_checks(runtime)

    assert lines == ["[warning] careful"]


async def test_routes_with_registered_router():
    from fastapi import APIRouter

    from fastkit_core.runtime import Runtime

    class Settings:
        installed_apps = []

    runtime = Runtime(settings=Settings(), installed_apps=[])
    runtime.routers.include(APIRouter(), prefix="/demo", source="demo")

    lines = await commands.routes_list(runtime)

    assert lines == ["/demo (from demo)"]


async def test_health_empty():
    from fastkit_core.runtime import Runtime

    class Settings:
        installed_apps = []

    runtime = Runtime(settings=Settings(), installed_apps=[])

    assert await commands.health_report(runtime) == ["no health checks registered"]


def test_build_parser_requires_group():
    with pytest.raises(SystemExit):
        build_parser().parse_args([])


def test_main_entry(monkeypatch, capsys, apps_map, runtime_factory):
    monkeypatch.setattr("fastkit_core.runtime.discover_apps", lambda: apps_map)

    exit_code = main(["apps", "list"], runtime_factory=runtime_factory)

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "fastkit.core" in captured.out
