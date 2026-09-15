"""A public form carries a challenge, and what the environment declares is what it carries."""

import base64
import random
import re

import httpx
import pytest

from enums.captcha import CaptchaProvider
from helpers import captcha
from helpers.settings import settings
from helpers.signing import unsign

FORMS = ["/account/login", "/account/signup", "/account/password-recovery", "/contact"]


@pytest.fixture
def drawing(monkeypatch):
    monkeypatch.setattr(settings.captcha, "provider", CaptchaProvider.IMAGE)


def answer_of(body: str) -> tuple[str, str]:
    """What a person reads off the image, which the token carries signed so nothing has to be kept between two requests."""
    token = re.search(r'name="captcha_token" value="([^"]+)"', body).group(1)

    return token, unsign("captcha", token)["word"]


@pytest.mark.parametrize("path", FORMS)
async def test_every_public_form_draws_the_challenge_the_environment_declares(site, drawing, path):
    body = (await site.get(path)).text

    assert 'name="captcha_token"' in body
    assert 'src="data:image/png;base64,' in body


@pytest.mark.parametrize("path", FORMS)
async def test_a_form_of_an_environment_that_declares_none_draws_none(site, path):
    assert 'name="captcha_token"' not in (await site.get(path)).text


async def test_the_drawn_challenge_is_a_readable_image(drawing):
    challenge = captcha.issue()
    payload = challenge.image.split(",", 1)[1]

    assert base64.b64decode(payload).startswith(b"\x89PNG")


async def test_a_form_answered_correctly_goes_through(site, drawing, member):
    body = (await site.get("/account/login")).text
    token, word = answer_of(body)

    answer = await site.post("/account/login", data={"csrf_token": re.search(r'name="csrf_token" value="([^"]+)"', body).group(1), "login": member.email, "password": "s3cret-password", "captcha_token": token, "captcha_answer": word.lower()}, follow_redirects=False)

    assert answer.status_code == 303


async def test_a_form_answered_wrongly_draws_itself_again_with_the_reason(site, drawing, member):
    """A page of the site never leaves as a body of JSON, so a challenge answered wrongly is the form drawn again."""
    body = (await site.get("/account/login")).text
    token, _ = answer_of(body)

    answer = await site.post("/account/login", data={"csrf_token": re.search(r'name="csrf_token" value="([^"]+)"', body).group(1), "login": member.email, "password": "s3cret-password", "captcha_token": token, "captcha_answer": "nope"})

    assert answer.status_code == 422
    assert answer.headers["content-type"].startswith("text/html")
    assert "The challenge was not answered correctly." in answer.text

    # A challenge is good for one attempt, so the form that comes back carries another one.
    assert answer_of(answer.text)[0] != token


@pytest.mark.parametrize(
    "path, payload",
    [("/contact", {"name": "Ada", "email": "ada@acme.com", "message": "I would like to know more."}), ("/newsletter", {"email": "ada@acme.com"}), ("/account/signup", {"first_name": "Ada", "email": "ada@acme.com", "password": "s3cret-password"}), ("/account/password-recovery", {"login": "ada@acme.com"})],
)
async def test_every_public_form_draws_itself_again_when_the_challenge_is_not_answered(site, drawing, path, payload):
    body = (await site.get(path)).text
    token, _ = answer_of(body)
    sent = {"csrf_token": re.search(r'name="csrf_token" value="([^"]+)"', body).group(1), "captcha_token": token, "captcha_answer": "nope", **payload}

    answer = await site.post(path, data=sent)

    assert answer.status_code == 422
    assert answer.headers["content-type"].startswith("text/html")
    assert "The challenge was not answered correctly." in answer.text


async def test_the_word_is_not_drawn_by_a_generator_somebody_can_follow(drawing, monkeypatch):
    """A word out of the mersenne twister is one whose state an attacker reconstructs, which leaves the challenge guarding nothing."""
    monkeypatch.setattr(random, "choice", lambda alphabet: pytest.fail("the word came out of the predictable generator"))

    words = {unsign("captcha", captcha.issue().token)["word"] for _ in range(20)}

    assert len(words) == 20


async def test_a_token_nobody_signed_is_refused(drawing):
    assert await captcha.verify("anything", "made.up", None) is False


async def test_a_token_that_expired_is_refused(monkeypatch, drawing):
    from datetime import timedelta

    from helpers import signing

    challenge = captcha.issue()
    word = unsign("captcha", challenge.token)["word"]

    monkeypatch.setattr(signing, "now", lambda: __import__("helpers.dates", fromlist=["now"]).now() + timedelta(seconds=settings.captcha.ttl + 1))

    assert await captcha.verify(word, challenge.token, None) is False


async def test_a_challenge_with_no_answer_is_refused(drawing):
    challenge = captcha.issue()

    assert await captcha.verify("", challenge.token, None) is False


async def test_an_environment_that_declares_none_lets_everything_through():
    assert await captcha.verify(None, None, None) is True


@pytest.fixture
def scored(monkeypatch):
    monkeypatch.setattr(settings.captcha, "provider", CaptchaProvider.RECAPTCHA_V3)
    monkeypatch.setattr(settings.captcha, "site_key", "site-key-1")
    monkeypatch.setattr(settings.captcha, "secret_key", "secret-key-1")


def answering(monkeypatch, status: int, body: dict):
    async def responder(self, request):
        return httpx.Response(status, json=body)

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", responder)


async def test_recaptcha_draws_its_site_key_and_nothing_else(site, scored):
    body = (await site.get("/account/login")).text

    assert 'data-recaptcha-site-key="site-key-1"' in body
    assert 'name="captcha_token"' not in body


async def test_a_visit_google_scores_high_enough_passes(monkeypatch, scored):
    answering(monkeypatch, 200, {"success": True, "score": 0.9})

    assert await captcha.verify("token-from-the-page", None, "203.0.113.1") is True


async def test_a_visit_google_scores_too_low_is_refused(monkeypatch, scored):
    answering(monkeypatch, 200, {"success": True, "score": 0.1})

    assert await captcha.verify("token-from-the-page", None, None) is False


async def test_a_visit_google_did_not_accept_is_refused(monkeypatch, scored):
    answering(monkeypatch, 200, {"success": False, "error-codes": ["invalid-input-response"]})

    assert await captcha.verify("token-from-the-page", None, None) is False


async def test_a_google_that_did_not_answer_is_a_refusal_and_never_a_pass(monkeypatch, scored):
    """A network that did not answer is not a visitor that passed."""
    answering(monkeypatch, 500, {})

    assert await captcha.verify("token-from-the-page", None, None) is False


async def test_a_page_that_sent_no_token_is_refused(scored):
    assert await captcha.verify("", None, None) is False


async def test_the_admin_draws_the_challenge_the_environment_declares(client, drawing):
    """The admin is a form somebody types into, so it carries the same challenge every public form does."""
    challenge = (await client.get("/api/meta/captcha")).json()

    assert challenge["provider"] == "image"
    assert challenge["image"].startswith("data:image/png;base64,")
    assert unsign("captcha", challenge["token"])["word"]


async def test_the_admin_challenge_carries_the_site_key_when_google_scores_it(client, scored):
    challenge = (await client.get("/api/meta/captcha")).json()

    assert challenge == {"provider": "recaptcha_v3", "token": "", "image": "", "siteKey": "site-key-1"}


async def test_the_admin_sign_in_refuses_the_wrong_answer(client, drawing, administrator):
    challenge = (await client.get("/api/meta/captcha")).json()

    answer = await client.post("/api/admin/signin", json={"login": "root", "password": "s3cret-password", "captchaAnswer": "nope", "captchaToken": challenge["token"]})

    assert answer.status_code == 422
    assert answer.json()["code"] == "error.captcha-invalid"
    assert "captchaAnswer" in answer.json()["errors"]


async def test_the_admin_sign_in_goes_through_once_it_is_answered(client, drawing, administrator):
    challenge = (await client.get("/api/meta/captcha")).json()
    word = unsign("captcha", challenge["token"])["word"]

    answer = await client.post("/api/admin/signin", json={"login": "root", "password": "s3cret-password", "captchaAnswer": word.lower(), "captchaToken": challenge["token"]})

    assert answer.status_code == 200
    assert answer.json()["token"]


@pytest.mark.parametrize("score", ["high", None, {"nested": 1}])
async def test_a_score_nothing_can_read_is_a_refusal_and_never_a_pass(monkeypatch, scored, score):
    """Anything but a clean answer is a refusal, and a body that cannot be read is not a visitor that passed."""
    answering(monkeypatch, 200, {"success": True, "score": score})

    assert await captcha.verify("token-from-the-page", None, None) is False
