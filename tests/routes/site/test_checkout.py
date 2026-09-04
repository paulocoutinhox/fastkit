"""What sends a buyer to the gateway, and the row this side writes before they ever leave."""

from urllib.parse import parse_qsl

import httpx
import pytest
from sqlalchemy import func, select

from enums.commerce import PurchaseStatus
from enums.integration import Provider
from helpers.security import encrypt
from models.commerce import Purchase
from tests.conftest import opened
from tests.factories import make_external_product, make_integration, make_plan, make_product, make_purchase


@pytest.fixture
def stripe(monkeypatch):
    calls = []

    async def answering(self, request):
        calls.append(dict(parse_qsl(request.content.decode())))

        return httpx.Response(200, json={"id": "cs_test_1", "url": "https://checkout.stripe.com/c/pay/cs_test_1"})

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", answering)

    return calls


@pytest.fixture
async def wired(db, tenant):
    return await make_integration(db, tenant, provider=Provider.STRIPE, stripe_api_key_encrypted=encrypt("sk_test_1"))


async def test_buying_a_product_writes_the_purchase_and_sends_the_buyer_to_the_gateway(signed_in, db, tenant, stripe, wired):
    product = await make_product(db, tenant, name="The Handbook", slug="handbook")
    token = await opened(signed_in, "/products/handbook")

    answer = await signed_in.post("/checkout/product/handbook", data={"csrf_token": token}, follow_redirects=False)

    assert answer.status_code == 303
    assert answer.headers["location"].startswith("https://checkout.stripe.com/")

    purchase = await db.scalar(select(Purchase))

    assert purchase.product_id == product.id
    assert stripe[0]["client_reference_id"] == purchase.reference
    assert stripe[0]["mode"] == "payment"


async def test_subscribing_sends_the_buyer_to_the_price_the_gateway_knows(signed_in, db, tenant, stripe, wired):
    plan = await make_plan(db, tenant, code="monthly")
    product = await make_external_product(db, wired, plan)
    token = await opened(signed_in, "/plans")

    answer = await signed_in.post("/checkout/plan/monthly", data={"csrf_token": token}, follow_redirects=False)

    assert answer.status_code == 303
    assert stripe[0]["mode"] == "subscription"
    assert stripe[0]["line_items[0][price]"] == product.external_id


async def test_a_checkout_names_the_account_so_the_notice_can_find_it_again(signed_in, db, tenant, member, stripe, wired):
    await make_product(db, tenant, slug="handbook")
    token = await opened(signed_in, "/products/handbook")

    await signed_in.post("/checkout/product/handbook", data={"csrf_token": token}, follow_redirects=False)

    assert stripe[0]["metadata[account_token]"] == member.token


async def test_a_visitor_with_no_session_is_sent_to_the_sign_in(site, db, tenant, wired):
    """Coming back from the sign in is a GET, so the destination is the page the form was drawn on and never the address it posts to."""
    await make_product(db, tenant, slug="handbook")
    token = await opened(site, "/products/handbook")

    answer = await site.post("/checkout/product/handbook", data={"csrf_token": token}, headers={"referer": "http://acme.test/products/handbook"}, follow_redirects=False)

    assert answer.status_code == 303
    assert answer.headers["location"] == "/account/login?next=%2Fproducts%2Fhandbook"

    landed = await site.get(answer.headers["location"].split("?")[0], follow_redirects=False)

    assert landed.status_code == 200


async def test_a_tenant_with_no_gateway_says_so_instead_of_breaking(signed_in, db, tenant):
    await make_product(db, tenant, slug="handbook")
    token = await opened(signed_in, "/products/handbook")

    answer = await signed_in.post("/checkout/product/handbook", data={"csrf_token": token}, follow_redirects=False)

    assert answer.status_code == 303
    assert answer.headers["location"] == "/products/handbook"
    assert await db.scalar(select(func.count()).select_from(Purchase)) == 0


async def test_a_plan_the_gateway_does_not_sell_says_so_instead_of_breaking(signed_in, db, tenant, wired):
    await make_plan(db, tenant, code="monthly")
    token = await opened(signed_in, "/plans")

    answer = await signed_in.post("/checkout/plan/monthly", data={"csrf_token": token}, follow_redirects=False)

    assert answer.status_code == 303
    assert answer.headers["location"] == "/plans"


async def test_a_gateway_that_refuses_the_session_says_so_instead_of_breaking(signed_in, db, tenant, wired, monkeypatch):
    async def refusing(self, request):
        return httpx.Response(402, json={"error": {"message": "no"}})

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", refusing)

    await make_product(db, tenant, slug="handbook")
    token = await opened(signed_in, "/products/handbook")

    answer = await signed_in.post("/checkout/product/handbook", data={"csrf_token": token}, follow_redirects=False)

    assert answer.status_code == 303
    assert answer.headers["location"] == "/products/handbook"

    # No session opened means the buyer never left, so the row this side wrote is not one waiting on a notice.
    purchase = await db.scalar(select(Purchase))

    assert purchase.status == PurchaseStatus.FAILED


async def test_a_purchase_no_gateway_ever_saw_is_not_left_on_the_page_of_the_buyer(signed_in, db, tenant, wired, monkeypatch):
    """A refused session left a row reading `pending` for good, on the purchases of the account and in the grid."""

    async def refusing(self, request):
        return httpx.Response(402, json={"error": {"message": "no"}})

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", refusing)

    await make_product(db, tenant, slug="handbook")
    token = await opened(signed_in, "/products/handbook")
    await signed_in.post("/checkout/product/handbook", data={"csrf_token": token}, follow_redirects=False)

    pending = await db.scalar(select(func.count()).select_from(Purchase).where(Purchase.status == PurchaseStatus.PENDING))

    assert pending == 0


async def test_a_product_that_names_nothing_is_not_a_checkout(signed_in, wired):
    token = await opened(signed_in, "/account")

    assert (await signed_in.post("/checkout/product/nothing", data={"csrf_token": token})).status_code == 404


async def test_a_plan_that_names_nothing_is_not_a_checkout(signed_in, wired):
    token = await opened(signed_in, "/account")

    assert (await signed_in.post("/checkout/plan/nothing", data={"csrf_token": token})).status_code == 404


async def test_the_gateway_sends_the_buyer_back_to_a_page_that_says_what_happened(site):
    paid = await site.get("/checkout/success")
    refused = await site.get("/checkout/error")

    assert "Payment received" in paid.text
    assert "did not go through" in refused.text


async def test_the_page_the_buyer_lands_on_is_named_after_the_row_it_should_read(signed_in, db, tenant, stripe, wired):
    await make_product(db, tenant, name="The Handbook", slug="handbook")
    token = await opened(signed_in, "/products/handbook")

    await signed_in.post("/checkout/product/handbook", data={"csrf_token": token}, follow_redirects=False)

    purchase = await db.scalar(select(Purchase))

    # The whole address and not its ending, because a gateway sends the buyer to exactly this and `//checkout/success` answers 404.
    assert stripe[0]["success_url"] == f"http://{tenant.domain}/checkout/success?purchase={purchase.reference}"
    assert stripe[0]["cancel_url"] == f"http://{tenant.domain}/checkout/error"

    assert (await signed_in.get(f"/checkout/success?purchase={purchase.reference}")).status_code == 200


@pytest.mark.parametrize("status,expected", [(PurchaseStatus.PAID, "Payment received"), (PurchaseStatus.PENDING, "Payment on its way"), (PurchaseStatus.ANALYSIS, "Payment on its way"), (PurchaseStatus.FAILED, "The payment did not go through")])
async def test_the_landing_page_says_what_the_purchase_actually_is(signed_in, db, tenant, member, status, expected):
    """A boleto sends the buyer back before it is paid, so a page that always says received would be lying."""
    product = await make_product(db, tenant)
    purchase = await make_purchase(db, tenant, member, product, status=status)

    answer = await signed_in.get(f"/checkout/success?purchase={purchase.reference}")

    assert expected in answer.text


async def test_a_subscription_lands_on_the_page_the_gateway_sent_it_to(signed_in):
    """A subscription writes no purchase of ours, so there is no row for the page to read."""
    assert "Payment received" in (await signed_in.get("/checkout/success")).text


async def test_the_purchase_of_somebody_else_is_not_read_by_whoever_names_it(signed_in, db, tenant, administrator):
    product = await make_product(db, tenant)
    purchase = await make_purchase(db, tenant, administrator, product, status=PurchaseStatus.PENDING)

    assert "Payment received" in (await signed_in.get(f"/checkout/success?purchase={purchase.reference}")).text
