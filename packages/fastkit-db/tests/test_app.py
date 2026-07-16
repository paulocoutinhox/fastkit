import pytest_asyncio

from fastkit_core.app_config import CoreApp
from fastkit_core.health.base import HealthStatus
from fastkit_core.runtime import Runtime
from fastkit_db.app import DbApp
from fastkit_db.engine import Database
from fastkit_db.repository import Repository
from fastkit_db.uow import UnitOfWork


class DbSettings:
    class database:
        url = "sqlite+aiosqlite:///:memory:"
        pool_pre_ping = True
        echo = False

    installed_apps = ["fastkit.core", "fastkit.db"]


@pytest_asyncio.fixture
async def runtime(monkeypatch):
    monkeypatch.setattr("fastkit_core.runtime.discover_apps", lambda: {"fastkit.core": CoreApp, "fastkit.db": DbApp})
    runtime = Runtime(settings=DbSettings(), installed_apps=["fastkit.core", "fastkit.db"])
    runtime.bootstrap()

    yield runtime

    await runtime.stop()


async def test_db_app_registers_database_component(runtime):
    database = runtime.component("database")

    assert isinstance(database, Database)
    assert runtime.component("metadata") is not None


async def test_db_app_health_check_reports_healthy(runtime):
    report = await runtime.health.run()

    assert report.status is HealthStatus.healthy


async def test_db_app_health_check_reports_unavailable(runtime):
    database = runtime.component("database")
    await database.dispose()
    await database.engine.dispose()

    monkeypatched = await _force_unavailable(runtime)

    assert monkeypatched.status is HealthStatus.unavailable


async def _force_unavailable(runtime):
    from fastkit_db.app import _database_health

    class BrokenEngine:
        def connect(self):
            raise RuntimeError("down")

    class BrokenDatabase:
        engine = BrokenEngine()

    return await _database_health(BrokenDatabase())


async def test_db_app_shutdown_without_database_is_noop():
    from fastkit_core.apps.base import BootstrapContext

    runtime = Runtime(settings=DbSettings(), installed_apps=[])
    context = BootstrapContext(runtime)

    await DbApp().shutdown(context)


async def test_repository_list_without_order_by(session, widget):
    repo = Repository(widget, session)
    await repo.add(widget(name="one"))

    items = await repo.list()

    assert len(items) == 1


async def test_unit_of_work_async_after_commit_hook(database, widget):
    calls: list[str] = []

    async def hook():
        calls.append("async")

    async with UnitOfWork(database.session_factory) as uow:
        uow.session.add(widget(name="async-hook"))
        uow.on_after_commit(hook)

    assert calls == ["async"]
