import pytest

from fastkit_core.apps.base import FastKitApp
from fastkit_core.apps.loader import AppLoadError, instantiate_selected, order_apps


class CoreApp(FastKitApp):
    name = "core"


class DbApp(FastKitApp):
    name = "db"
    requires = ("core",)


class AuthApp(FastKitApp):
    name = "auth"
    requires = ("db",)


def available():
    return {"core": CoreApp, "db": DbApp, "auth": AuthApp}


def test_instantiate_selected_returns_instances():
    apps = instantiate_selected(["core", "db"], available())

    assert [app.name for app in apps] == ["core", "db"]


def test_instantiate_selected_duplicate_raises():
    with pytest.raises(AppLoadError, match="duplicate app"):
        instantiate_selected(["core", "core"], available())


def test_instantiate_selected_unknown_raises():
    with pytest.raises(AppLoadError, match="not installed"):
        instantiate_selected(["ghost"], available())


def test_order_respects_dependencies():
    apps = instantiate_selected(["auth", "core", "db"], available())
    ordered = order_apps(apps)

    assert [app.name for app in ordered] == ["core", "db", "auth"]


def test_order_missing_requirement_raises():
    apps = instantiate_selected(["db"], {"db": DbApp})

    with pytest.raises(AppLoadError, match="requires 'core'"):
        order_apps(apps)


def test_order_detects_cycle():
    class A(FastKitApp):
        name = "a"
        requires = ("b",)

    class B(FastKitApp):
        name = "b"
        requires = ("a",)

    apps = [A(), B()]

    with pytest.raises(AppLoadError, match="circular"):
        order_apps(apps)
