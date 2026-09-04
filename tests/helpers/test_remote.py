"""What another machine answered is read as a map or as nothing, because a body nobody can parse is not a yes."""

import httpx
import pytest

from helpers import remote
from helpers.errors import AppError
from services.checkout import checkout_service


def answered(body: bytes, content_type: str = "application/json") -> httpx.Response:
    return httpx.Response(200, content=body, headers={"content-type": content_type})


def test_a_body_that_is_a_map_is_the_map():
    assert remote.body_of(answered(b'{"url": "https://gateway.acme.com/x"}')) == {"url": "https://gateway.acme.com/x"}


@pytest.mark.parametrize("body", [b"<html>maintenance</html>", b"", b"[1, 2, 3]", b'"a string"', b"null"])
def test_a_body_that_is_not_a_map_is_nothing_at_all(body):
    """A gateway behind a proxy answers 200 with a page, and reading that as an answer is how a 500 reaches a buyer."""
    assert remote.body_of(answered(body, "text/html")) == {}


async def test_a_captcha_answered_with_something_unreadable_is_a_refusal(monkeypatch):
    """The rule is that anything but a clean pass is a refusal, and a 200 nobody can parse is not a clean pass."""
    from helpers import captcha
    from helpers.settings import settings

    monkeypatch.setattr(settings.captcha, "provider", "recaptcha_v3")
    monkeypatch.setattr(settings.captcha, "secret_key", "secret")

    async def answer(self, *args, **kwargs):
        return answered(b"<html>down</html>", "text/html")

    monkeypatch.setattr(httpx.AsyncClient, "post", answer)

    assert await captcha.verify("token", None, None) is False


async def test_a_postal_code_answered_with_something_unreadable_is_not_found(monkeypatch):
    from helpers import postal_code

    async def answer(self, *args, **kwargs):
        return answered(b"<html>down</html>", "text/html")

    monkeypatch.setattr(httpx.AsyncClient, "get", answer)

    assert await postal_code.ViaCep().find("01001000") is None


async def test_a_checkout_the_gateway_never_named_a_session_for_is_refused(db, tenant, member, monkeypatch):
    """A 200 with no address is a session that was never opened, and sending a buyer nowhere is worse than saying so."""
    from tests.factories import make_integration, make_product

    integration = await make_integration(db, tenant)
    product = await make_product(db, tenant)

    monkeypatch.setattr(checkout_service, "gateway_of", lambda *args: _answered(integration))

    async def answer(self, *args, **kwargs):
        return answered(b"{}")

    monkeypatch.setattr(httpx.AsyncClient, "post", answer)
    monkeypatch.setattr("services.integration.integration_service.read_secret", lambda integration: "sk_test")

    with pytest.raises(AppError) as refused:
        await checkout_service.for_product(db, tenant, member, product, "https://acme.com/ok", "https://acme.com/no")

    assert refused.value.code == "error.checkout-refused"


async def _answered(value):
    return value
