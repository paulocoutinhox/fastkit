from datetime import timedelta

import pytest
from sqlalchemy import select

from enums.account import CreditTransactionType
from enums.subscription import UserEntitlementStatus
from helpers.dates import now
from helpers.storage import storage
from models.subscription import UserEntitlement
from models.user import User
from services.account import credit_transaction_service
from tests.factories import make_currency, make_entitlement, make_plan, make_product, make_purchase, make_subscription
from tests.routes.test_upload import PNG


@pytest.fixture
def mailed(monkeypatch):
    """The token leaves by mail, so a test that wants it reads the row and never the answer."""
    sent = []

    async def capture(db, tenant_id, to, subject, template, **context):
        sent.append(to)

    monkeypatch.setattr("services.auth.email_service.queue", capture)

    return sent


async def test_read_me(client, member, member_headers):
    response = await client.get("/api/account/me", headers=member_headers)

    assert response.status_code == 200
    assert response.json()["username"] == "reader"


async def test_read_me_requires_a_token(client, member):
    response = await client.get("/api/account/me")

    assert response.status_code == 401


async def test_read_me_refuses_a_broken_token(client, member):
    response = await client.get("/api/account/me", headers={"Authorization": "Bearer not-a-token"})

    assert response.status_code == 401
    assert response.json()["code"] == "error.invalid-token"


async def test_update_me(client, member, member_headers):
    response = await client.put("/api/account/me", json={"firstName": "Ada", "nickname": "ada"}, headers=member_headers)

    assert response.status_code == 200
    assert response.json()["firstName"] == "Ada"


async def test_the_account_never_names_a_stored_file(client, member, member_headers):
    """A file column is what the next save deletes, so naming a key here would let an account erase an image the whole site reads."""
    response = await client.put("/api/account/me", json={"avatar": "images/banner/2026/01/01/a-real-banner.jpg"}, headers=member_headers)

    assert response.status_code == 422
    assert response.json()["errors"]["avatar"]


async def test_an_administrator_still_only_names_a_key_of_the_avatar_folder(client, member, admin_headers):
    """The admin posts a key too, and one pointing outside that folder deletes whatever it points at on the next save."""
    response = await client.put(f"/api/users/{member.id}", json={"avatar": "images/banner/2026/01/01/a-real-banner.jpg"}, headers=admin_headers)

    assert response.status_code == 422
    assert response.json()["code"] == "error.upload-key-out-of-purpose"


async def test_the_account_sends_its_picture_and_reads_it_back_in_one_call(client, member, member_headers):
    """Two calls meant the client handled a storage key, and a key a client holds is a key it can point anywhere."""
    response = await client.post("/api/account/avatar", files={"file": ("me.png", PNG, "image/png")}, headers=member_headers)

    assert response.status_code == 200
    assert response.json()["avatarUrl"].endswith(".webp")


async def test_sending_another_picture_discards_the_one_before(client, member, member_headers):
    first = await client.post("/api/account/avatar", files={"file": ("me.png", PNG, "image/png")}, headers=member_headers)
    second = await client.post("/api/account/avatar", files={"file": ("other.png", PNG, "image/png")}, headers=member_headers)

    assert first.json()["avatarUrl"] != second.json()["avatarUrl"]
    assert await storage.read(first.json()["avatarUrl"].split("/media/")[-1]) is None


async def test_removing_the_picture_answers_an_account_without_one(client, member, member_headers):
    await client.post("/api/account/avatar", files={"file": ("me.png", PNG, "image/png")}, headers=member_headers)

    response = await client.delete("/api/account/avatar", headers=member_headers)

    assert response.status_code == 200
    assert response.json()["avatarUrl"] is None


async def test_removing_a_picture_that_was_never_sent_changes_nothing(client, member, member_headers):
    response = await client.delete("/api/account/avatar", headers=member_headers)

    assert response.status_code == 200
    assert response.json()["avatarUrl"] is None


async def test_update_me_refuses_an_unknown_timezone(client, member, member_headers):
    response = await client.put("/api/account/me", json={"timezone": "Mars/Olympus"}, headers=member_headers)

    assert response.status_code == 422


async def test_change_password(client, member, member_headers, tenant_headers):
    response = await client.post("/api/account/password", json={"currentPassword": "s3cret-password", "newPassword": "another-password"}, headers=member_headers)

    assert response.status_code == 200

    signin = await client.post("/api/signin", json={"login": "reader", "password": "another-password"}, headers=tenant_headers)

    assert signin.status_code == 200


async def test_change_password_refuses_a_wrong_current_one(client, member, member_headers):
    response = await client.post("/api/account/password", json={"currentPassword": "wrong-password", "newPassword": "another-password"}, headers=member_headers)

    assert response.status_code == 422
    assert response.json()["code"] == "error.current-password-invalid"


async def test_password_reset_flow(client, db, member, tenant_headers, mailed):
    started = await client.post("/api/account/password-reset", json={"login": "reader"}, headers=tenant_headers)

    assert started.status_code == 204

    token = await db.scalar(select(User.recovery_token).where(User.id == member.id))
    confirmed = await client.post("/api/account/password-reset/confirm", json={"token": token, "newPassword": "brand-new-password"})

    assert confirmed.status_code == 204

    signin = await client.post("/api/signin", json={"login": "reader", "password": "brand-new-password"}, headers=tenant_headers)

    assert signin.status_code == 200


async def test_password_reset_hides_an_unknown_login(client, tenant, tenant_headers, mailed):
    response = await client.post("/api/account/password-reset", json={"login": "nobody"}, headers=tenant_headers)

    assert response.status_code == 204
    assert mailed == []


async def test_password_reset_refuses_an_unknown_token(client, member):
    response = await client.post("/api/account/password-reset/confirm", json={"token": "not-a-token", "newPassword": "brand-new-password"})

    assert response.status_code == 422
    assert response.json()["code"] == "error.recovery-token-invalid"


async def test_password_reset_refuses_an_expired_token(client, db, member, tenant_headers, mailed):
    await client.post("/api/account/password-reset", json={"login": "reader"}, headers=tenant_headers)

    await db.refresh(member)
    token = member.recovery_token
    member.recovery_token_created_at = now() - timedelta(days=1)
    await db.commit()

    response = await client.post("/api/account/password-reset/confirm", json={"token": token, "newPassword": "brand-new-password"})

    assert response.status_code == 422
    assert response.json()["code"] == "error.recovery-token-expired"


async def test_erase_me(client, member, member_headers, tenant_headers):
    response = await client.delete("/api/account/me", headers=member_headers)

    assert response.status_code == 204

    signin = await client.post("/api/signin", json={"login": "reader", "password": "s3cret-password"}, headers=tenant_headers)

    assert signin.status_code == 401


async def test_list_credits(client, db, member, member_headers, currency):
    await credit_transaction_service.move(db, member.id, currency.id, CreditTransactionType.CREDIT, 10, "welcome", "key-1", None, {})

    response = await client.get("/api/account/credits", headers=member_headers)

    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert response.json()["items"][0]["balanceAfter"] == 10


async def build_entitled(db, tenant, member, **overrides):
    plan = await make_plan(db, tenant)
    entitlement = await make_entitlement(db, tenant, code="premium", name="Premium")
    subscription = await make_subscription(db, tenant, member, plan)

    db.add(UserEntitlement(subscription_id=subscription.id, entitlement_id=entitlement.id, meta={}, **overrides))
    await db.commit()

    return entitlement


async def test_an_account_with_no_subscription_is_entitled_to_nothing(client, member_headers):
    assert (await client.get("/api/account/entitlements", headers=member_headers)).json()["items"] == []


async def test_the_entitlements_answer_the_code_an_app_gates_by(client, db, tenant, member, member_headers):
    await build_entitled(db, tenant, member)

    items = (await client.get("/api/account/entitlements", headers=member_headers)).json()["items"]

    assert [item["code"] for item in items] == ["premium"]
    assert items[0]["name"] == "Premium"
    assert items[0]["status"] == "active"


async def test_an_expired_entitlement_still_travels_with_its_status(client, db, tenant, member, member_headers):
    await build_entitled(db, tenant, member, status=UserEntitlementStatus.EXPIRED)

    items = (await client.get("/api/account/entitlements", headers=member_headers)).json()["items"]

    assert items[0]["status"] == "expired"


async def test_one_account_never_sees_the_entitlements_of_another(client, db, tenant, member, admin_headers):
    await build_entitled(db, tenant, member)

    assert (await client.get("/api/account/entitlements", headers=admin_headers)).json()["items"] == []


async def test_the_account_is_named_by_a_token_and_never_by_its_id(client, member, member_headers):
    """The id is the admin's way of naming a record, and nothing the app reads has any use for it."""
    response = await client.get("/api/account/me", headers=member_headers)
    body = response.json()

    assert body["token"] == member.token
    assert "id" not in body
    assert "userId" not in body


async def test_the_token_is_born_with_the_account_and_is_unique_across_the_database(db, tenant):
    """It names an account in any scope, so two tenants can never answer for the same one."""
    from enums.user import UserRole, UserStatus
    from services.user import user_service
    from tests.factories import make_tenant

    other = await make_tenant(db, code="outra", name="Outra")
    first = await user_service.create(db, {"username": "um", "password": "s3cret-password", "role": UserRole.NORMAL, "status": UserStatus.ACTIVE, "tenant_id": tenant.id})
    second = await user_service.create(db, {"username": "um", "password": "s3cret-password", "role": UserRole.NORMAL, "status": UserStatus.ACTIVE, "tenant_id": other.id})

    assert first.token
    assert second.token
    assert first.token != second.token


async def test_a_session_is_resolved_by_the_token_the_account_carries(client, db, member, tenant_headers):
    """The JWT names the account by its token, so nothing readable inside it points at a row."""
    import jwt as pyjwt

    response = await client.post("/api/signin", json={"login": "reader", "password": "s3cret-password"}, headers=tenant_headers)
    claims = pyjwt.decode(response.json()["token"], options={"verify_signature": False})

    assert claims["sub"] == member.token
    assert str(member.id) != claims["sub"]


async def test_the_wallet_ledger_never_names_the_account_it_belongs_to(client, db, member, member_headers, currency):
    from enums.account import CreditTransactionType
    from services.account import credit_transaction_service

    await credit_transaction_service.move(db, member.id, currency.id, CreditTransactionType.CREDIT, 10, "welcome", "k-1", None, {})

    items = (await client.get("/api/account/credits", headers=member_headers)).json()["items"]

    assert len(items) == 1
    assert "userId" not in items[0]
    assert "user" not in items[0]


async def test_the_app_reads_what_the_store_holds_the_moment_it_asks(client, db, tenant, member, member_headers, monkeypatch):
    """A five minute sandbox subscription is only usable if the answer is immediate, so this never waits for a webhook."""
    import httpx

    from enums.integration import Provider
    from helpers.dates import now
    from helpers.security import encrypt
    from models.integration import ExternalProduct
    from tests.factories import make_integration, make_plan, save

    integration = await make_integration(db, tenant, provider=Provider.REVENUECAT, revenuecat_api_key_encrypted=encrypt("sk"))
    plan = await make_plan(db, tenant)

    await save(db, ExternalProduct(integration_id=integration.id, plan_id=plan.id, external_id="mensal", active=True, meta={}))

    async def answering(self, request):
        ends = (now() + timedelta(days=30)).isoformat().replace("+00:00", "Z")

        return httpx.Response(200, json={"subscriber": {"subscriptions": {"mensal": {"expires_date": ends, "period_type": "NORMAL", "store": "APP_STORE", "is_sandbox": True, "store_transaction_id": "txn-1", "purchase_date": ends}}}})

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", answering)

    response = await client.post("/api/account/subscriptions/refresh", headers=member_headers)
    items = response.json()["items"]

    assert response.status_code == 200
    assert len(items) == 1
    assert items[0]["status"] == "active"
    assert "userId" not in items[0]


async def test_the_account_reads_what_it_paid_for(client, db, member, tenant, member_headers):
    product = await make_product(db, tenant, name="Deck")
    await make_purchase(db, tenant, member, product)

    answer = await client.get("/api/account/purchases", headers=member_headers)

    assert answer.status_code == 200
    assert [item["product"]["name"] for item in answer.json()["items"]] == ["Deck"]


async def test_the_statement_of_purchases_answers_only_the_caller(client, db, member, tenant, administrator, member_headers):
    product = await make_product(db, tenant, name="Deck")
    await make_purchase(db, tenant, administrator, product)

    assert (await client.get("/api/account/purchases", headers=member_headers)).json()["count"] == 0


async def test_the_account_reads_what_it_holds_of_each_currency(client, db, member, currency, member_headers):
    """The product decides how many currencies it has, so the account answers a list and never a pair of columns."""
    gems = await make_currency(db, code="gem", name="Gems")

    await credit_transaction_service.move(db, member.id, currency.id, CreditTransactionType.CREDIT, 40, None, "coins", None, {})
    await credit_transaction_service.move(db, member.id, gems.id, CreditTransactionType.CREDIT, 7, None, "gems", None, {})

    answer = await client.get("/api/account/balances", headers=member_headers)

    assert [(row["currency"]["code"], row["amount"]) for row in answer.json()["items"]] == [("coin", 40), ("gem", 7)]


async def test_a_reader_cannot_kill_the_process_with_a_small_picture(client, member_headers):
    """A canvas of eighty million pixels weighs a few hundred kilobytes on the wire and hundreds of megabytes once decoded."""
    import io

    from PIL import Image

    frame = io.BytesIO()
    Image.new("L", (9000, 9000), 0).save(frame, format="PNG")
    bomb = frame.getvalue()

    assert len(bomb) < 512 * 1024

    answer = await client.post("/api/account/avatar", files={"file": ("huge.png", bomb, "image/png")}, headers=member_headers)

    assert answer.status_code == 422
    assert answer.json()["code"] == "error.upload-image-too-large"


async def test_a_picture_goes_with_the_write_that_did_not_go_through(client, db, member, member_headers, monkeypatch):
    """The file is written before the row that claims it, which is what every framework that uploads first has to answer for."""
    from services import user as user_module

    async def refuse(session, code="error.duplicated-record"):
        raise RuntimeError("the row was never written")

    monkeypatch.setattr(user_module, "commit", refuse)

    before = {key async for key in storage.walk()}

    with pytest.raises(RuntimeError):
        await client.post("/api/account/avatar", files={"file": ("me.png", PNG, "image/png")}, headers=member_headers)

    after = {key async for key in storage.walk()}

    assert after == before, f"the write did not go through and these were left behind: {sorted(after - before)}"
    assert (await db.get(User, member.id)).avatar is None
