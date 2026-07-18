import pytest
import pytest_asyncio

from fastkit_core.app_config import CoreApp
from fastkit_core.runtime import Runtime
from fastkit_db.app import DbApp
from fastkit_tenancy.app import TenancyApp
from fastkit_accounts.app import AccountsApp
from fastkit_auth.app import AuthApp
from fastkit_i18n.app import I18nApp
from fastkit_content.app import ContentApp

APPS = {
    "fastkit.core": CoreApp,
    "fastkit.db": DbApp,
    "fastkit.tenancy": TenancyApp,
    "fastkit.accounts": AccountsApp,
    "fastkit.auth": AuthApp,
    "fastkit.i18n": I18nApp,
    "fastkit.content": ContentApp,
}


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
        secret_key = "cli-secret-key-1234567890"

    class database:
        url = "sqlite+aiosqlite:///:memory:"
        pool_pre_ping = True
        echo = False

    class auth:
        password_min_length = 12
        password_max_length = 128
        jwt_algorithm = "HS256"
        access_token_ttl_seconds = 3600
        max_failed_logins = 5
        lockout_seconds = 900
        rate_limit_per_minute = 10
        captcha = Captcha()

    class i18n:
        default_locale = "en"
        supported_locales = ["en", "pt", "es"]

    installed_apps = list(APPS.keys())


def make_runtime():
    return Runtime(settings=Settings(), installed_apps=list(APPS.keys()))


@pytest.fixture
def apps_map():
    return dict(APPS)


@pytest.fixture
def runtime_factory():
    return make_runtime


@pytest_asyncio.fixture
async def runtime(monkeypatch, tmp_path):
    from fastkit_db.base import Base

    monkeypatch.setattr("fastkit_core.runtime.discover_apps", lambda: dict(APPS))
    Settings.database.url = f"sqlite+aiosqlite:///{tmp_path}/cli.db"

    runtime = make_runtime()
    runtime.bootstrap()
    await runtime.component("database").create_all(Base.metadata)

    yield runtime

    await runtime.stop()
