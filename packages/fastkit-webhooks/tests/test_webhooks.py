import json

import pytest
import pytest_asyncio

from fastkit_core.app_config import CoreApp
from fastkit_core.runtime import Runtime
from fastkit_db.app import DbApp
from fastkit_webhooks.app import WebhooksApp
from fastkit_webhooks.models import WebhookEvent, WebhookStatus
from fastkit_webhooks.provider import HmacWebhookProvider, RawWebhookRequest
from fastkit_webhooks.service import WebhookRegistry, WebhookService
from fastkit_webhooks.signature import compute_signature, verify_signature


def _body(event_id="evt_1", event_type="payment.succeeded"):
    return json.dumps({"id": event_id, "type": event_type, "account_id": "acct_1"}).encode("utf-8")


def test_signature_helpers():
    body = b"payload"
    signature = compute_signature("secret", body)

    assert verify_signature("secret", body, signature)
    assert not verify_signature("secret", body, "wrong")
    assert not verify_signature("secret", body, None)


def test_registry_errors():
    registry = WebhookRegistry()
    registry.register(HmacWebhookProvider("a", "s"))

    with pytest.raises(ValueError, match="already registered"):
        registry.register(HmacWebhookProvider("a", "s"))

    with pytest.raises(KeyError, match="not registered"):
        registry.get("missing")


async def test_provider_verify_and_normalize(signer):
    provider = HmacWebhookProvider("stripe", "whsec_test", "X-Signature")
    body = _body()
    request = RawWebhookRequest(headers={"X-Signature": signer(body)}, body=body)

    assert (await provider.verify(request)).valid is True

    normalized = await provider.normalize(request)
    assert normalized.external_event_id == "evt_1"
    assert normalized.provider_account_id == "acct_1"
    assert normalized.event_type == "payment.succeeded"


async def test_receive_valid_webhook(service, signer):
    body = _body()
    event, created = await service.receive("stripe", {"X-Signature": signer(body)}, body)

    assert created is True
    assert event.signature_valid is True
    assert event.status == WebhookStatus.received.value
    assert event.event_type == "payment.succeeded"


async def test_receive_is_idempotent(service, signer):
    body = _body()
    headers = {"X-Signature": signer(body)}

    first, created_first = await service.receive("stripe", headers, body)
    second, created_second = await service.receive("stripe", headers, body)

    assert created_first is True
    assert created_second is False
    assert first.id == second.id


async def test_concurrent_receive_is_idempotent(service, signer):
    import asyncio

    body = _body()
    headers = {"X-Signature": signer(body)}

    results = await asyncio.gather(*[service.receive("stripe", headers, body) for _ in range(6)])
    created = [was_created for _, was_created in results]

    assert created.count(True) == 1
    assert len({event.id for event, _ in results}) == 1


async def test_receive_rejects_invalid_signature(service):
    body = _body()
    event, created = await service.receive("stripe", {"X-Signature": "forged"}, body)

    assert event.signature_valid is False
    assert event.status == WebhookStatus.rejected.value
    assert event.last_error_code == "webhook.invalid_signature"


async def test_receive_rejects_missing_signature(service):
    body = _body()
    event, _ = await service.receive("stripe", {}, body)

    assert event.status == WebhookStatus.rejected.value


async def test_replaying_a_rejected_webhook_is_idempotent(service):
    body = _body()

    first, _ = await service.receive("stripe", {"X-Signature": "forged"}, body)
    second, _ = await service.receive("stripe", {"X-Signature": "forged"}, body)

    assert second.id == first.id
    assert second.status == WebhookStatus.rejected.value


async def test_valid_signature_over_a_malformed_body_is_rejected_not_a_500(service, signer):
    body = b"this is not json"
    event, handled = await service.receive("stripe", {"X-Signature": signer(body)}, body)

    assert handled is True
    assert event.status == WebhookStatus.rejected.value
    assert "malformed payload" in event.last_error_message


async def test_valid_signature_over_a_non_object_json_body_is_rejected(service, signer):
    body = b"[1, 2, 3]"
    event, handled = await service.receive("stripe", {"X-Signature": signer(body)}, body)

    assert handled is True
    assert event.status == WebhookStatus.rejected.value


async def test_process_success(service, signer):
    body = _body()
    event, _ = await service.receive("stripe", {"X-Signature": signer(body)}, body)

    seen = {}

    async def handler(webhook):
        seen["type"] = webhook.event_type

    processed = await service.process(event.id, handler)

    assert processed.status == WebhookStatus.processed.value
    assert processed.attempt_count == 1
    assert seen["type"] == "payment.succeeded"


async def test_process_does_not_run_twice_for_an_already_claimed_event(service, signer):
    body = _body()
    event, _ = await service.receive("stripe", {"X-Signature": signer(body)}, body)

    calls = []

    async def handler(webhook):
        calls.append(webhook.id)

    await service.process(event.id, handler)
    again = await service.process(event.id, handler)

    assert calls == [event.id]
    assert again.status == WebhookStatus.processed.value
    assert again.attempt_count == 1


async def test_process_without_handler(service, signer):
    body = _body()
    event, _ = await service.receive("stripe", {"X-Signature": signer(body)}, body)

    processed = await service.process(event.id)

    assert processed.status == WebhookStatus.processed.value


async def test_process_retries_then_fails(service, signer):
    body = _body()
    event, _ = await service.receive("stripe", {"X-Signature": signer(body)}, body)

    async def broken(webhook):
        raise RuntimeError("downstream error")

    first = await service.process(event.id, broken, max_attempts=2)
    assert first.status == WebhookStatus.retrying.value

    second = await service.process(event.id, broken, max_attempts=2)
    assert second.status == WebhookStatus.failed.value
    assert second.last_error_code == "webhook.processing_failed"


class Settings:
    class database:
        url = "sqlite+aiosqlite:///:memory:"
        pool_pre_ping = True
        echo = False

    installed_apps = ["fastkit.core", "fastkit.db", "fastkit.webhooks"]


@pytest_asyncio.fixture
async def runtime(monkeypatch):
    monkeypatch.setattr("fastkit_core.runtime.discover_apps", lambda: {"fastkit.core": CoreApp, "fastkit.db": DbApp, "fastkit.webhooks": WebhooksApp})
    runtime = Runtime(settings=Settings(), installed_apps=list(Settings.installed_apps))
    runtime.bootstrap()

    yield runtime

    await runtime.stop()


async def test_webhooks_app_registers(runtime):
    assert WebhookEvent in runtime.models.all()
    assert isinstance(runtime.component("webhook_service"), WebhookService)
    assert isinstance(runtime.component("webhook_registry"), WebhookRegistry)
