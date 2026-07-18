import pytest

from fastkit_core.apps.base import FastKitApp
from fastkit_core.checks.base import CheckLevel, CheckMessage
from fastkit_core.runtime import Runtime


class RecordingApp(FastKitApp):
    name = "recording"

    def __init__(self):
        self.events: list[str] = []

    def register_settings(self, context):
        self.events.append("settings")

    def register_models(self, context):
        self.events.append("models")

    def register_services(self, context):
        self.events.append("services")

    def register_routers(self, context):
        self.events.append("routers")

    def register_checks(self, context):
        self.events.append("checks")

    async def startup(self, context):
        self.events.append("startup")

    async def shutdown(self, context):
        self.events.append("shutdown")


class Settings:
    installed_apps = ["recording"]


def build_runtime(monkeypatch, app):
    runtime = Runtime(settings=Settings(), installed_apps=["recording"])
    monkeypatch.setattr(
        "fastkit_core.runtime.discover_apps", lambda: {"recording": lambda: app}
    )

    return runtime


async def test_bootstrap_and_lifecycle_order(monkeypatch):
    app = RecordingApp()
    runtime = build_runtime(monkeypatch, app)

    runtime.bootstrap()

    assert app.events[:3] == ["settings", "models", "services"]
    assert "routers" in app.events and "checks" in app.events

    await runtime.start()
    assert runtime.ready
    assert app.events[-1] == "startup"

    await runtime.stop()
    assert not runtime.ready
    assert app.events[-1] == "shutdown"


def test_registry_is_created_lazily():
    runtime = Runtime(settings=Settings(), installed_apps=[])
    registry = runtime.registry("providers")

    assert runtime.registry("providers") is registry


def test_component_registration_and_missing():
    runtime = Runtime(settings=Settings(), installed_apps=[])

    assert runtime.try_component("db") is None
    runtime.set_component("db", object())
    assert runtime.component("db") is not None

    with pytest.raises(KeyError, match="not registered"):
        runtime.component("missing")


def test_failing_check_aborts_bootstrap(monkeypatch):
    class FailingApp(FastKitApp):
        name = "recording"

        def register_checks(self, context):
            context.checks.register(
                "bad", lambda: [CheckMessage(CheckLevel.error, "nope")]
            )

    runtime = build_runtime(monkeypatch, FailingApp())

    with pytest.raises(Exception, match="system checks failed"):
        runtime.bootstrap()
