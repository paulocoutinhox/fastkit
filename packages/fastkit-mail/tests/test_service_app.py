import sys
import types

import pytest
import pytest_asyncio

from fastkit_core.app_config import CoreApp
from fastkit_core.runtime import Runtime
from fastkit_db.app import DbApp
from fastkit_mail.app import MailApp, build_provider, build_renderer
from fastkit_mail.memory import MemoryEmailProvider
from fastkit_mail.models import DeliveryStatus, EmailDelivery
from fastkit_mail.service import MailService
from fastkit_mail.smtp import SmtpEmailProvider, build_mime
from fastkit_mail.provider import EmailMessage


async def test_send_template_success(service, provider):
    delivery = await service.send_template(
        "accounts.welcome", ["a@b.c"], {"user_name": "Ada", "app_name": "Acme"}
    )

    assert delivery.status == DeliveryStatus.sent.value
    assert delivery.provider_message_id == "mem-1"
    assert len(provider.sent) == 1
    assert provider.sent[0].subject == "Welcome to Acme"


async def test_preview_does_not_send(service, provider):
    rendered = service.preview(
        "accounts.welcome", {"user_name": "Ada", "app_name": "Acme"}
    )

    assert rendered.subject == "Welcome to Acme"
    assert provider.sent == []


async def test_send_retries_then_fails(database, renderer):
    provider = MemoryEmailProvider(fail=True)
    service = MailService(database, renderer, provider, "memory", "no-reply@x")

    delivery = await service.send_template(
        "accounts.welcome", ["a@b.c"], {"user_name": "Ada", "app_name": "Acme"}
    )
    assert delivery.status == DeliveryStatus.retrying.value

    delivery = await service.retry(delivery.id)
    assert delivery.status == DeliveryStatus.retrying.value

    delivery = await service.retry(delivery.id)
    assert delivery.status == DeliveryStatus.failed.value
    assert delivery.last_error_code == "email.send_failed"


class RaisingProvider:
    def __init__(self):
        self.calls = 0

    async def send(self, message):
        self.calls += 1

        raise ConnectionError("smtp unreachable")


async def test_send_survives_provider_exception(database, renderer):
    from fastkit_core.resilience import CircuitBreaker

    provider = RaisingProvider()
    breaker = CircuitBreaker(failure_threshold=2)
    service = MailService(
        database, renderer, provider, "smtp", "no-reply@x", breaker=breaker
    )

    delivery = await service.send_template(
        "accounts.welcome", ["a@b.c"], {"user_name": "Ada", "app_name": "Acme"}
    )

    assert delivery.status == DeliveryStatus.retrying.value
    assert delivery.last_error_message == "smtp unreachable"
    assert provider.calls == 1


async def test_open_circuit_skips_provider(database, renderer):
    from fastkit_core.resilience import CircuitBreaker

    provider = RaisingProvider()
    breaker = CircuitBreaker(failure_threshold=1, reset_after_seconds=1000)
    breaker.record_failure()
    service = MailService(
        database, renderer, provider, "smtp", "no-reply@x", breaker=breaker
    )

    delivery = await service.send_template(
        "accounts.welcome", ["a@b.c"], {"user_name": "Ada", "app_name": "Acme"}
    )

    assert delivery.status == DeliveryStatus.retrying.value
    assert "circuit is open" in delivery.last_error_message
    assert provider.calls == 0


async def test_memory_provider_health():
    assert (await MemoryEmailProvider().health()).status.value == "healthy"
    assert (await MemoryEmailProvider(fail=True).health()).status.value == "unavailable"


def test_build_mime_has_alternatives():
    message = EmailMessage(
        to=["a@b.c"],
        subject="Hi",
        html_body="<p>x</p>",
        text_body="x",
        from_email="f@x",
        cc=["c@d.e"],
        reply_to="r@x",
    )
    mime = build_mime(message)

    assert mime["To"] == "a@b.c"
    assert mime["Cc"] == "c@d.e"
    assert mime["Reply-To"] == "r@x"


class Settings:
    class app:
        environment = "dev"

    class database:
        url = "sqlite+aiosqlite:///:memory:"
        pool_pre_ping = True
        pool_recycle = 1800
        echo = False

    class mail:
        provider = "memory"
        host = "localhost"
        port = 1025
        username = ""
        password = ""
        use_tls = False
        default_from = "no-reply@fastkit.local"

    installed_apps = ["fastkit.core", "fastkit.db", "fastkit.mail"]


def _mail_settings(provider):
    return types.SimpleNamespace(
        mail=types.SimpleNamespace(
            provider=provider,
            host="localhost",
            port=1025,
            username="",
            password="",
            use_tls=False,
            default_from="no-reply@x",
        )
    )


def test_build_provider_memory():
    assert isinstance(build_provider(_mail_settings("memory")), MemoryEmailProvider)


def test_build_provider_smtp():
    assert isinstance(build_provider(_mail_settings("smtp")), SmtpEmailProvider)


def test_build_provider_unknown():
    with pytest.raises(ValueError, match="unknown mail provider"):
        build_provider(_mail_settings("carrier-pigeon"))


def test_build_renderer_prepends_project_dirs():
    renderer = build_renderer(["/project/templates"])

    assert renderer._environment.loader.searchpath[0] == "/project/templates"


@pytest_asyncio.fixture
async def runtime(monkeypatch):
    monkeypatch.setattr(
        "fastkit_core.runtime.discover_apps",
        lambda: {"fastkit.core": CoreApp, "fastkit.db": DbApp, "fastkit.mail": MailApp},
    )
    runtime = Runtime(settings=Settings(), installed_apps=list(Settings.installed_apps))
    runtime.bootstrap()

    yield runtime

    await runtime.stop()


async def test_mail_app_registers(runtime):
    assert EmailDelivery in runtime.models.all()
    assert isinstance(runtime.component("mail_service"), MailService)


async def test_smtp_provider_send_and_health(monkeypatch):
    sent = {}

    fake_module = types.ModuleType("aiosmtplib")

    async def fake_send(mime, **kwargs):
        sent["kwargs"] = kwargs

    class FakeSMTP:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def connect(self):
            return None

        async def quit(self):
            return None

    fake_module.send = fake_send
    fake_module.SMTP = FakeSMTP
    monkeypatch.setitem(sys.modules, "aiosmtplib", fake_module)

    provider = SmtpEmailProvider(host="localhost", port=1025)
    message = EmailMessage(
        to=["a@b.c"],
        subject="Hi",
        html_body="<p>x</p>",
        text_body="x",
        from_email="f@x",
    )

    result = await provider.send(message)
    assert result.success is True
    assert sent["kwargs"]["hostname"] == "localhost"

    assert (await provider.health()).status.value == "healthy"


async def test_smtp_provider_send_failure(monkeypatch):
    fake_module = types.ModuleType("aiosmtplib")

    async def fake_send(mime, **kwargs):
        raise ConnectionError("no server")

    class FakeSMTP:
        def __init__(self, **kwargs):
            pass

        async def connect(self):
            raise ConnectionError("no server")

        async def quit(self):
            return None

    fake_module.send = fake_send
    fake_module.SMTP = FakeSMTP
    monkeypatch.setitem(sys.modules, "aiosmtplib", fake_module)

    provider = SmtpEmailProvider(host="localhost", port=1025)
    message = EmailMessage(
        to=["a@b.c"],
        subject="Hi",
        html_body="<p>x</p>",
        text_body="x",
        from_email="f@x",
    )

    result = await provider.send(message)
    assert result.success is False
    assert (await provider.health()).status.value == "unavailable"
