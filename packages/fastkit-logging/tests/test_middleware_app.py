import logging

import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient

from fastkit_core.app_config import CoreApp
from fastkit_core.runtime import Runtime
from fastkit_logging.app import LoggingApp
from fastkit_logging.middleware import RequestLoggingMiddleware
from fastkit_logging.models import AuditLog, SystemLog
from fastkit_logging.service import AuditLogService, SystemLogService
from fastkit_db.app import DbApp


def build_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestLoggingMiddleware)

    @app.get("/ok")
    async def ok():
        return {"ok": True}

    @app.get("/boom")
    async def boom():
        raise RuntimeError("kaboom")

    return app


def test_middleware_logs_success(caplog):
    with caplog.at_level(logging.INFO, logger="fastkit.request"):
        TestClient(build_app()).get("/ok")

    assert any(
        "request GET /ok -> 200" in record.getMessage() for record in caplog.records
    )


def test_middleware_logs_failure(caplog):
    client = TestClient(build_app(), raise_server_exceptions=False)

    with caplog.at_level(logging.ERROR, logger="fastkit.request"):
        client.get("/boom")

    assert any("request failed" in record.getMessage() for record in caplog.records)


class LogSettings:
    class app:
        name = "Demo"
        environment = "test"

    class database:
        url = "sqlite+aiosqlite:///:memory:"
        pool_pre_ping = True
        echo = False

    class logging:
        level = "INFO"
        file = "logs/test-app.log"

    installed_apps = ["fastkit.core", "fastkit.db", "fastkit.logging"]


@pytest_asyncio.fixture
async def runtime(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "fastkit_core.runtime.discover_apps",
        lambda: {
            "fastkit.core": CoreApp,
            "fastkit.db": DbApp,
            "fastkit.logging": LoggingApp,
        },
    )

    settings = LogSettings()
    settings.logging.file = str(tmp_path / "app.log")

    runtime = Runtime(settings=settings, installed_apps=list(settings.installed_apps))
    runtime.bootstrap()

    yield runtime

    await runtime.stop()


async def test_logging_app_registers_models_and_services(runtime):
    registered = runtime.models.all()

    assert SystemLog in registered
    assert AuditLog in registered
    assert isinstance(runtime.component("system_log_service"), SystemLogService)
    assert isinstance(runtime.component("audit_log_service"), AuditLogService)
