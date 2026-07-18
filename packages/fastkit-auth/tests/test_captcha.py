import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi import APIRouter, FastAPI

from fastkit_core.errors.exceptions import AuthenticationError
from fastkit_auth.captcha.disabled import DisabledCaptchaProvider
from fastkit_auth.captcha.provider import CaptchaProvider
from fastkit_auth.captcha.image import ImageCaptchaProvider
from fastkit_auth.captcha.providers import captcha_providers
from fastkit_auth.captcha.recaptcha import (
    RecaptchaConfig,
    RecaptchaProvider,
    StaticRecaptchaClient,
)
from fastkit_auth.store import MemoryKeyValueStore


def _recaptcha(
    action="admin_login", score=0.5, hostnames=(), response=None, store=None
):
    config = RecaptchaConfig(
        action=action, minimum_score=score, allowed_hostnames=hostnames
    )

    return RecaptchaProvider(
        config,
        StaticRecaptchaClient(response or {}),
        "site-key",
        store or MemoryKeyValueStore(),
    )


async def _image_code(provider, store, challenge_id):
    stored = await store.get(provider._store_key(challenge_id))

    return json.loads(stored.decode("utf-8"))["code"]


async def test_disabled_captcha_passes_and_hides_itself():
    provider = DisabledCaptchaProvider()

    assert provider.enabled is False
    assert provider.client_config()["provider"] is None
    await provider.verify(None)


async def test_base_provider_defaults():
    class Minimal(CaptchaProvider):
        @property
        def enabled(self):
            return True

        async def verify(self, payload):
            return None

    provider = Minimal()

    assert provider.client_config() == {"provider": "captcha", "enabled": True}
    assert provider.mount_routes(APIRouter()) is None


async def test_recaptcha_requires_a_token():
    with pytest.raises(AuthenticationError, match="required"):
        await _recaptcha(response={"success": True}).verify(None)


async def test_recaptcha_success_and_client_config():
    provider = _recaptcha(
        hostnames=("admin.example.com",),
        response={
            "success": True,
            "action": "admin_login",
            "score": 0.9,
            "hostname": "admin.example.com",
        },
    )

    assert provider.enabled is True
    await provider.verify({"token": "token-1"})

    config = provider.client_config()
    assert config["provider"] == "recaptcha"
    assert config["site_key"] == "site-key"
    assert "recaptcha/api.js" in config["script_url"]


async def test_recaptcha_rejects_a_replayed_token():
    provider = _recaptcha(
        response={"success": True, "action": "admin_login", "score": 0.9}
    )

    await provider.verify({"token": "token-1"})

    with pytest.raises(AuthenticationError, match="already used"):
        await provider.verify({"token": "token-1"})


@pytest.mark.parametrize(
    "response,message",
    [
        ({"success": False}, "verification failed"),
        ({"success": True, "action": "other", "score": 0.9}, "action mismatch"),
        ({"success": True, "action": "admin_login", "score": 0.2}, "score too low"),
    ],
)
async def test_recaptcha_rejects_bad_responses(response, message):
    with pytest.raises(AuthenticationError, match=message):
        await _recaptcha(score=0.5, response=response).verify({"token": "t"})


async def test_recaptcha_hostname_mismatch():
    provider = _recaptcha(
        hostnames=("admin.example.com",),
        response={
            "success": True,
            "action": "admin_login",
            "score": 0.9,
            "hostname": "evil.com",
        },
    )

    with pytest.raises(AuthenticationError, match="hostname mismatch"):
        await provider.verify({"token": "t"})


async def test_recaptcha_provider_unavailable():
    class BrokenClient:
        async def verify(self, token):
            raise RuntimeError("network down")

    provider = RecaptchaProvider(
        RecaptchaConfig(action="admin_login", minimum_score=0.5, allowed_hostnames=()),
        BrokenClient(),
        "k",
        MemoryKeyValueStore(),
    )

    with pytest.raises(AuthenticationError, match="unavailable"):
        await provider.verify({"token": "t"})


async def test_recaptcha_rejects_a_non_numeric_score():
    provider = _recaptcha(
        response={"success": True, "action": "admin_login", "score": "abc"}
    )

    with pytest.raises(AuthenticationError, match="score invalid"):
        await provider.verify({"token": "t"})


class _Clock:
    def __init__(self):
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now = self.now + timedelta(seconds=seconds)


async def test_image_captcha_full_flow():
    clock = _Clock()
    store = MemoryKeyValueStore()
    provider = ImageCaptchaProvider(store, length=5, ttl_seconds=300, clock=clock)

    assert provider.enabled is True
    assert provider.client_config() == {
        "provider": "image",
        "enabled": True,
        "new_url": "/auth/captcha/new",
    }

    challenge = await provider.new_challenge()
    assert challenge["image"].startswith("data:image/png;base64,")

    code = await _image_code(provider, store, challenge["challenge_id"])
    await provider.verify(
        {"challenge_id": challenge["challenge_id"], "answer": code.lower()}
    )

    # a challenge is single-use
    with pytest.raises(AuthenticationError, match="unknown"):
        await provider.verify(
            {"challenge_id": challenge["challenge_id"], "answer": code}
        )


async def test_image_captcha_requires_id_and_answer():
    provider = ImageCaptchaProvider(MemoryKeyValueStore())

    with pytest.raises(AuthenticationError, match="required"):
        await provider.verify({"challenge_id": "x"})


async def test_image_captcha_unknown_challenge():
    provider = ImageCaptchaProvider(MemoryKeyValueStore())

    with pytest.raises(AuthenticationError, match="unknown"):
        await provider.verify({"challenge_id": "missing", "answer": "ABCDE"})


async def test_image_captcha_rejects_wrong_and_expired():
    clock = _Clock()
    store = MemoryKeyValueStore(clock=lambda: clock().timestamp())
    provider = ImageCaptchaProvider(store, ttl_seconds=100, clock=clock)

    wrong = await provider.new_challenge()
    with pytest.raises(AuthenticationError, match="incorrect"):
        await provider.verify(
            {"challenge_id": wrong["challenge_id"], "answer": "nope-nope"}
        )

    expired = await provider.new_challenge()
    code = await _image_code(provider, store, expired["challenge_id"])
    clock.advance(120)
    with pytest.raises(AuthenticationError, match="expired"):
        await provider.verify({"challenge_id": expired["challenge_id"], "answer": code})


async def test_image_captcha_mounts_a_new_challenge_route():
    provider = ImageCaptchaProvider(MemoryKeyValueStore())
    router = APIRouter()
    provider.mount_routes(router)
    app = FastAPI()
    app.include_router(router)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        body = (await client.get("/auth/captcha/new")).json()

    assert body["data"]["image"].startswith("data:image/png;base64,")


def test_registry_builds_each_built_in():
    from types import SimpleNamespace

    captcha = SimpleNamespace(
        provider="image",
        site_key="s",
        secret_key="",
        action="admin_login",
        minimum_score=0.5,
        allowed_hostnames=[],
        timeout_seconds=5,
        image_length=4,
        challenge_ttl_seconds=60,
    )
    settings = SimpleNamespace(auth=SimpleNamespace(captcha=captcha))
    store = MemoryKeyValueStore()

    assert isinstance(
        captcha_providers.build("disabled", settings, store), DisabledCaptchaProvider
    )
    assert isinstance(
        captcha_providers.build("image", settings, store), ImageCaptchaProvider
    )
    assert isinstance(
        captcha_providers.build("recaptcha", settings, store), RecaptchaProvider
    )

    captcha.secret_key = "real-secret"
    from fastkit_auth.captcha.recaptcha import GoogleRecaptchaClient

    assert isinstance(
        captcha_providers.build("recaptcha", settings, store)._client,
        GoogleRecaptchaClient,
    )
