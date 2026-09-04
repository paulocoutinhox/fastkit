from enums.user import UserRole
from helpers.settings import settings
from routes.meta import CATALOG


async def test_health(client):
    response = await client.get("/api/meta/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_meta_answers_what_the_admin_needs(client):
    response = await client.get("/api/meta")

    assert response.status_code == 200

    body = response.json()

    assert body["environment"] == "dev"
    assert body["version"] == settings.version
    assert body["languages"] == {"en": "English", "pt": "Português", "es": "Español"}
    assert "UTC" in body["timezones"]
    assert body["captcha"] == {"provider": "disabled", "siteKey": ""}


async def test_every_enum_of_the_domain_is_published(client):
    response = await client.get("/api/meta")

    published = response.json()["enums"]

    assert set(published) == set(CATALOG)
    assert published["user_role"] == [role.value for role in UserRole]
    assert published["purchase_status"] == ["pending", "analysis", "paid", "canceled", "failed", "refunded", "charged_back"]


async def test_the_name_of_the_product_is_answered_and_never_written_twice(client, monkeypatch):
    """The panel, the api documentation, the mailer and the command line all call it the same, so one value says what it is called."""
    monkeypatch.setattr(settings, "name", "Acme Panel")

    assert (await client.get("/api/meta")).json()["name"] == "Acme Panel"
