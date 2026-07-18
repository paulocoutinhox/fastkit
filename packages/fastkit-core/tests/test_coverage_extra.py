from types import SimpleNamespace

from fastapi import APIRouter
from fastapi.testclient import TestClient

from fastkit_core.apps.base import BootstrapContext, FastKitApp
from fastkit_core.apps.loader import discover_apps
from fastkit_core.errors.codes import DATABASE_ERROR
from fastkit_core.errors.exceptions import FastKitError, InternalError
from fastkit_core.runtime import Runtime


class Settings:
    installed_apps = []


def test_bootstrap_context_accessors():
    runtime = Runtime(settings=Settings(), installed_apps=[])
    context = BootstrapContext(runtime)

    assert context.registry("x") is runtime.registry("x")

    context.set_component("svc", 42)
    assert context.component("svc") == 42


def test_runtime_apps_property():
    runtime = Runtime(settings=Settings(), installed_apps=[])

    assert runtime.apps == []


def test_default_app_hooks_are_noops():
    app = FastKitApp()
    runtime = Runtime(settings=Settings(), installed_apps=[])
    context = BootstrapContext(runtime)

    app.register_translations(context)
    app.register_tasks(context)
    app.register_admin(context)
    app.register_settings(context)
    app.register_services(context)


def test_internal_error_uses_internal_code():
    assert InternalError("db down").error_code.code == "internal.error"


async def test_bare_app_startup_shutdown_noops():
    app = FastKitApp()
    runtime = Runtime(settings=Settings(), installed_apps=[])
    context = BootstrapContext(runtime)

    await app.startup(context)
    await app.shutdown(context)
    app.register_routers(context)
    app.register_checks(context)


def test_field_from_loc_root():
    from fastkit_core.errors.handlers import _field_from_loc

    assert _field_from_loc(("body",)) == ("__root__", ["__root__"])
    assert _field_from_loc(("body", "email")) == ("email", ["email"])


def test_discover_apps_reads_entry_points(monkeypatch):
    class FakeApp(FastKitApp):
        name = "fake"

    entry = SimpleNamespace(load=lambda: FakeApp)
    monkeypatch.setattr("fastkit_core.apps.loader.entry_points", lambda group: [entry])

    assert discover_apps()["fake"] is FakeApp


def test_logged_error_produces_error_id(error_app):
    router = APIRouter()

    @router.get("/db-error")
    async def db_error():
        raise FastKitError(DATABASE_ERROR, message="db down")

    error_app.include_router(router)
    body = TestClient(error_app, raise_server_exceptions=False).get("/db-error").json()

    assert body["meta"]["error_id"].startswith("ERR-")
    assert body["message"]["code"] == "database.error"


def test_validation_root_error(error_app):
    client = TestClient(error_app, raise_server_exceptions=False)

    response = client.post(
        "/validate", content=b"not-json", headers={"content-type": "application/json"}
    )

    assert response.status_code == 422
