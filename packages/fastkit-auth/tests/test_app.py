import pytest_asyncio

from fastkit_core.app_config import CoreApp
from fastkit_core.runtime import Runtime
from fastkit_db.app import DbApp
from fastkit_tenancy.app import TenancyApp
from fastkit_accounts.app import AccountsApp
import pytest

from fastkit_auth.app import AuthApp, build_captcha_provider, build_store
from fastkit_auth.captcha.disabled import DisabledCaptchaProvider
from fastkit_auth.captcha.recaptcha import GoogleRecaptchaClient, RecaptchaProvider
from fastkit_auth.models import Session
from fastkit_auth.service import AuthService
from fastkit_auth.store import MemoryKeyValueStore, SharedKeyValueStore


class Captcha:
    provider = "disabled"
    site_key = ""
    secret_key = ""
    action = "admin_login"
    minimum_score = 0.5
    allowed_hostnames = []
    timeout_seconds = 5
    image_length = 5
    challenge_ttl_seconds = 300


class Settings:
    class app:
        name = "Demo"
        environment = "test"
        secret_key = "demo-secret"

    class database:
        url = "sqlite+aiosqlite:///:memory:"
        pool_pre_ping = True
        pool_recycle = 1800
        echo = False

    class auth:
        password_min_length = 12
        password_max_length = 128
        jwt_algorithm = "HS256"
        access_token_ttl_seconds = 3600
        max_failed_logins = 5
        lockout_seconds = 900
        rate_limit_per_minute = 10
        store = "memory"
        captcha = Captcha()

    installed_apps = [
        "fastkit.core",
        "fastkit.db",
        "fastkit.tenancy",
        "fastkit.accounts",
        "fastkit.auth",
    ]


@pytest_asyncio.fixture
async def runtime(monkeypatch):
    monkeypatch.setattr(
        "fastkit_core.runtime.discover_apps",
        lambda: {
            "fastkit.core": CoreApp,
            "fastkit.db": DbApp,
            "fastkit.tenancy": TenancyApp,
            "fastkit.accounts": AccountsApp,
            "fastkit.auth": AuthApp,
        },
    )
    runtime = Runtime(settings=Settings(), installed_apps=list(Settings.installed_apps))
    runtime.bootstrap()

    yield runtime

    await runtime.stop()


async def test_auth_app_registers(runtime):
    assert Session in runtime.models.all()
    assert isinstance(runtime.component("auth_service"), AuthService)
    assert runtime.component("password_service") is not None
    assert runtime.component("token_service") is not None
    assert isinstance(runtime.component("captcha_provider"), DisabledCaptchaProvider)


def test_build_captcha_provider_selects_by_settings():
    settings = Settings()
    store = MemoryKeyValueStore()

    assert isinstance(build_captcha_provider(settings, store), DisabledCaptchaProvider)

    settings.auth.captcha.provider = "recaptcha"
    settings.auth.captcha.secret_key = "secret"

    assert isinstance(build_captcha_provider(settings, store), RecaptchaProvider)

    settings.auth.captcha.provider = "disabled"
    settings.auth.captcha.secret_key = ""


def test_build_store_selects_by_settings():
    from types import SimpleNamespace

    memory_settings = SimpleNamespace(auth=SimpleNamespace(store="memory"))
    assert isinstance(build_store(memory_settings, None), MemoryKeyValueStore)

    provider = object()
    context = SimpleNamespace(component=lambda name: provider)
    shared_settings = SimpleNamespace(auth=SimpleNamespace(store="shared"))
    store = build_store(shared_settings, context)
    assert isinstance(store, SharedKeyValueStore)
    assert store._resolve() is provider

    unknown_settings = SimpleNamespace(auth=SimpleNamespace(store="nope"))
    with pytest.raises(ValueError, match="unknown auth store"):
        build_store(unknown_settings, None)


async def test_google_recaptcha_client_posts(monkeypatch):
    captured = {}

    class FakeResponse:
        def json(self):
            return {"success": True, "score": 0.9}

    class FakeClient:
        def __init__(self, timeout):
            captured["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, data):
            captured["url"] = url
            captured["data"] = data

            return FakeResponse()

    import httpx

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

    client = GoogleRecaptchaClient("secret-key", timeout_seconds=3)
    result = await client.verify("token-123")

    assert result == {"success": True, "score": 0.9}
    assert captured["data"]["response"] == "token-123"
    assert captured["timeout"] == 3
