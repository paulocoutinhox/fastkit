"""One reader against the rows of another, because an identifier somebody typed is never a permission."""

import pytest
from httpx import ASGITransport, AsyncClient

from helpers.security import create_token
from services.user import user_service
from tests.factories import make_currency, make_plan, make_product, make_purchase, make_subscription


async def other_reader(db, tenant):
    return await user_service.create(db, {"tenant_id": tenant.id, "username": "stranger", "email": "stranger@acme.com", "password": "s3cret-password"})


async def test_a_reader_never_reaches_the_rows_of_another(app, db, tenant, member, admin_headers, tenant_headers):
    stranger = await other_reader(db, tenant)
    plan = await make_plan(db, tenant)
    theirs = await make_subscription(db, tenant, stranger, plan)
    product = await make_product(db, tenant)
    bought = await make_purchase(db, tenant, stranger, product)
    currency = await make_currency(db)

    mine = {"Authorization": f"Bearer {create_token(member.token, member.role, member.session_epoch)}", **tenant_headers}
    reached = []

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for name, path in [
            ("subscription transactions", f"/api/subscriptions/{theirs.id}/transactions"),
            ("subscription of another", f"/api/subscriptions/{theirs.id}"),
            ("purchase of another", f"/api/purchases/{bought.id}"),
            ("user of another", f"/api/users/{stranger.id}"),
            ("address of another", "/api/user-addresses"),
            ("balance of another", "/api/user-balances"),
            ("ledger of another", "/api/credit-transactions"),
        ]:
            answer = await client.get(path, headers=mine)

            if answer.status_code == 200:
                reached.append(f"{name}: {path} answered {answer.json()}")

    assert reached == [], f"a reader reached what is not theirs: {reached}"
    assert currency.id


async def test_what_the_account_lists_is_only_ever_its_own(app, db, tenant, member, tenant_headers):
    """Every listing of `/api/account` is scoped by the session, so a second account changes nothing about the first."""
    stranger = await other_reader(db, tenant)
    plan = await make_plan(db, tenant)
    await make_subscription(db, tenant, stranger, plan)
    product = await make_product(db, tenant)
    await make_purchase(db, tenant, stranger, product)

    mine = {"Authorization": f"Bearer {create_token(member.token, member.role, member.session_epoch)}", **tenant_headers}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for path in ["/api/account/purchases", "/api/account/products", "/api/account/entitlements", "/api/account/credits", "/api/account/balances", "/api/account/addresses", "/api/subscriptions/me"]:
            body = (await client.get(path, headers=mine)).json()
            rows = body["items"] if isinstance(body, dict) and "items" in body else body

            assert rows == [], f"{path} answered rows of somebody else: {rows}"


@pytest.mark.parametrize("path", ["/api/account/me", "/api/account/purchases", "/api/account/balances"])
async def test_a_header_naming_another_tenant_changes_nothing_about_the_account(app, db, tenant, member, path):
    """A session says who somebody is and a header says which brand they are reading, so the header never moves the account."""
    from tests.factories import make_tenant

    elsewhere = await make_tenant(db, code="elsewhere", domain="elsewhere.test")
    mine = {"Authorization": f"Bearer {create_token(member.token, member.role, member.session_epoch)}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        here = await client.get(path, headers={**mine, "X-Tenant-Code": tenant.code})
        there = await client.get(path, headers={**mine, "X-Tenant-Code": elsewhere.code})

    assert here.status_code == there.status_code == 200
    assert here.json() == there.json()


async def test_the_tenant_header_never_widens_what_a_catalogue_answers(app, db, tenant):
    """The header says which brand is being read, so a code somebody typed answers that brand and never another."""
    from tests.factories import make_product, make_tenant

    elsewhere = await make_tenant(db, code="elsewhere", domain="elsewhere.test")

    await make_product(db, tenant, name="Ours", slug="ours")
    await make_product(db, elsewhere, name="Theirs", slug="theirs")
    await make_product(db, None, name="Shared", slug="shared")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        here = {row["slug"] for row in (await client.get("/api/commerce/products", headers={"X-Tenant-Code": tenant.code})).json()["items"]}
        there = {row["slug"] for row in (await client.get("/api/commerce/products", headers={"X-Tenant-Code": elsewhere.code})).json()["items"]}

    assert here == {"ours", "shared"}
    assert there == {"theirs", "shared"}


async def test_a_reader_signed_in_elsewhere_reads_the_brand_the_header_names_and_nothing_of_their_own(app, db, tenant, member):
    """A session says who somebody is and the header says which brand they are reading, and neither one is the other."""
    from tests.factories import make_product, make_tenant

    elsewhere = await make_tenant(db, code="elsewhere", domain="elsewhere.test")

    await make_product(db, tenant, name="Ours", slug="ours")
    await make_product(db, elsewhere, name="Theirs", slug="theirs")

    mine = {"Authorization": f"Bearer {create_token(member.token, member.role, member.session_epoch)}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        answered = {row["slug"] for row in (await client.get("/api/commerce/products", headers={**mine, "X-Tenant-Code": elsewhere.code})).json()["items"]}

    assert answered == {"theirs"}, "the catalogue of another brand is public, and it carries nothing of the account reading it"


async def test_a_page_of_the_site_never_opens_the_row_of_another_account(signed_in, db, tenant, member):
    """The site resolves the number in the path against the session exactly like the API does."""
    from tests.factories import make_plan, make_product, make_purchase, make_subscription

    stranger = await other_reader(db, tenant)
    plan = await make_plan(db, tenant)
    theirs = await make_subscription(db, tenant, stranger, plan)
    product = await make_product(db, tenant)
    bought = await make_purchase(db, tenant, stranger, product)

    assert (await signed_in.get(f"/account/subscriptions/{theirs.id}")).status_code == 404
    assert (await signed_in.get(f"/account/purchases/{bought.id}")).status_code == 404


async def test_every_page_of_the_account_answers_only_the_session_that_asked(signed_in, db, tenant, member):
    """A listing of the site is scoped by the session, so a second account leaves every page of the first untouched."""
    from tests.factories import make_plan, make_product, make_purchase, make_subscription

    stranger = await other_reader(db, tenant)
    plan = await make_plan(db, tenant, name="Stranger plan")
    await make_subscription(db, tenant, stranger, plan)
    product = await make_product(db, tenant, name="Stranger product")
    await make_purchase(db, tenant, stranger, product)

    for path in ["/account", "/account/subscriptions", "/account/purchases", "/account/products", "/account/credits"]:
        body = (await signed_in.get(path)).text

        assert "Stranger" not in body, f"{path} drew a row of somebody else"
