"""An instance that serves one site holds no tenant at all, and the configuration is what says so."""

import secrets

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from starlette.requests import Request

from enums.integration import Provider
from enums.user import UserStatus
from helpers import brand
from helpers.auth import get_current_brand
from helpers.errors import AppError, ValidationError
from helpers.settings import settings
from helpers.site import brand_of
from models.integration import Integration
from models.newsletter import NewsletterSubscription
from services.user import user_service
from tests.conftest import opened
from tests.factories import save


@pytest.fixture
def single(monkeypatch):
    monkeypatch.setattr(settings, "multi_tenant", False)


def test_the_brand_of_a_single_site_is_the_one_the_configuration_declares(single):
    """A row is what carries the identity where there are many brands, and the configuration carries it where there is one."""
    only = brand.of(None)

    assert only.id is None
    assert only.name == settings.name
    assert only.domain == settings.site.domain
    assert only.email_contact == settings.email.from_address
    assert only.code == ""


async def test_a_single_site_answers_without_a_tenant_row_and_without_a_host(single, db, app):
    """The host is not asked because there is nothing to ask it against, so a machine with no dns still serves."""
    request = Request({"type": "http", "headers": [(b"host", b"nothing.example")], "method": "GET", "path": "/", "query_string": b"", "scheme": "http", "server": ("nothing.example", 80), "client": ("127.0.0.1", 1)})

    only = await brand_of(db, request)

    assert only is not None
    assert only.id is None


async def test_the_api_of_a_single_site_asks_for_no_header(single, db):
    only = await get_current_brand(db, None)

    assert only.id is None


async def test_the_api_of_a_single_site_refuses_a_header_that_names_one(single, db):
    """Naming a tenant to an instance that has none would be a second way of saying which site this is."""
    with pytest.raises(AppError):
        await get_current_brand(db, "acme")


async def test_where_many_brands_are_served_the_header_is_still_demanded(db):
    assert settings.multi_tenant is True

    with pytest.raises(ValidationError):
        await get_current_brand(db, None)


async def test_where_many_brands_are_served_an_unknown_one_is_refused(db):
    with pytest.raises(AppError):
        await get_current_brand(db, "nobody")


@pytest.fixture
async def only_site(single, app):
    """A host no tenant answers for, because in this mode there is no tenant for one to answer for."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://nothing.example") as instance:
        yield instance


async def test_a_single_site_draws_its_pages_for_a_host_nobody_registered(only_site):
    assert (await only_site.get("/")).status_code == 200
    assert (await only_site.get("/products")).status_code == 200
    assert (await only_site.get("/plans")).status_code == 200


async def test_a_single_site_is_named_by_the_configuration_and_not_by_a_row(only_site):
    page = await only_site.get("/")

    assert settings.name in page.text


async def test_a_single_site_still_has_a_sitemap(only_site):
    answer = await only_site.get("/sitemap.xml")

    assert answer.status_code == 200
    assert "<urlset" in answer.text


async def test_an_account_of_the_global_scope_signs_in_on_a_single_site(only_site, db):
    await user_service.create(db, {"tenant_id": None, "username": "reader", "email": "reader@acme.com", "password": "secret123", "status": UserStatus.ACTIVE})
    await db.commit()

    token = await opened(only_site, "/account/login")
    answer = await only_site.post("/account/login", data={"csrf_token": token, "login": "reader", "password": "secret123", "next": "/account"}, follow_redirects=False)

    assert answer.status_code == 303
    assert answer.headers["location"] == "/account"


async def test_what_a_single_site_writes_belongs_to_no_brand(only_site, db):
    """Every row of an instance serving one site sits in the global scope, which is what makes it need no tenant at all."""
    token = await opened(only_site, "/newsletter")
    await only_site.post("/newsletter", data={"csrf_token": token, "email": "reader@acme.com"})

    scoped = await db.scalar(select(func.count()).select_from(NewsletterSubscription).where(NewsletterSubscription.tenant_id.is_(None)))

    assert scoped == 1


async def test_a_record_named_after_its_brand_is_named_where_there_is_no_tenant_to_name(single, db, client, admin_headers):
    """The panel draws a label for every row it lists, and reading a tenant that does not exist is a screen that answers with a crash."""
    await save(db, Integration(tenant_id=None, provider=Provider.STRIPE, webhook_key=secrets.token_urlsafe(16), meta={}))

    answer = await client.get("/api/integrations/lookup", headers=admin_headers)

    assert answer.status_code == 200
    assert answer.json()["items"][0]["label"] == f"{settings.name} - Stripe"
