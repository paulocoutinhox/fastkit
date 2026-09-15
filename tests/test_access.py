"""What somebody tries to reach that is not theirs, attempted against the running application and refused."""

import asyncio
import time

import pytest
from sqlalchemy import func, select

from enums.user import UserRole, UserStatus
from helpers.crud import RESOURCES
from helpers.errors import AuthenticationError
from helpers.security import create_token, no_such_account
from services.auth import auth_service
from services.user import user_service
from tests.factories import make_product, make_purchase


@pytest.fixture
async def editor(db):
    return await user_service.create(db, {"username": "editor", "email": "editor@acme.com", "password": "s3cret-password", "role": UserRole.EDITOR, "status": UserStatus.ACTIVE})


@pytest.fixture
def editor_headers(editor):
    return {"Authorization": f"Bearer {create_token(editor.token, editor.role, editor.session_epoch)}"}


@pytest.fixture
async def stranger(db, tenant):
    return await user_service.create(db, {"username": "stranger", "email": "stranger@acme.com", "password": "s3cret-password", "role": UserRole.NORMAL, "status": UserStatus.ACTIVE, "tenant_id": tenant.id})


@pytest.fixture
def stranger_headers(stranger):
    return {"Authorization": f"Bearer {create_token(stranger.token, stranger.role, stranger.session_epoch)}"}


async def test_a_lookup_answers_a_name_and_never_a_row(client, editor_headers, tenant):
    """A catalogue is widened so a form can be filled, and what it hands over is an option and not the record behind it."""
    answer = await client.get("/api/tenants/lookup", headers=editor_headers)
    option = answer.json()["items"][0]

    assert answer.status_code == 200
    assert set(option) == {"id", "label"}
    assert tenant.domain not in str(answer.json())


@pytest.mark.parametrize("query", ["code=acme", "domain=acme.test", "id=1", "secret=x"])
async def test_a_lookup_is_not_a_way_to_ask_it_something_else(client, editor_headers, query):
    """A filter the listing never declared is refused rather than ignored, on a lookup exactly as on a list."""
    answer = await client.get(f"/api/tenants/lookup?{query}", headers=editor_headers)

    assert answer.status_code == 422
    assert answer.json()["code"] == "error.unknown-query-parameter"


async def test_the_catalogue_a_role_resolves_is_not_one_it_may_read(client, editor_headers):
    """Resolving an option and reading the rows are different permissions, and widening the first never widens the second."""
    assert (await client.get("/api/tenants/lookup", headers=editor_headers)).status_code == 200
    assert (await client.get("/api/tenants", headers=editor_headers)).status_code == 403
    assert (await client.get("/api/tenants/1", headers=editor_headers)).status_code == 403


@pytest.mark.parametrize("username", ["evil\nadmin deleted tenants 1", "with spaces", "<script>alert(1)</script>", "semi;colon", "quote'name"])
async def test_an_identity_carries_nothing_that_could_forge_a_line(client, admin_headers, username):
    """It is written into the record of what an operator did, and a line of that record is read as one line."""
    answer = await client.post("/api/users", json={"username": username, "email": "x@acme.com", "password": "s3cret-password"}, headers=admin_headers)

    assert answer.status_code == 422
    assert answer.json()["errors"]["username"]


async def test_signing_up_cannot_name_itself_anything_either(client, tenant_headers):
    answer = await client.post("/api/signup", json={"username": "evil\nname", "password": "s3cret-password"}, headers=tenant_headers)

    assert answer.status_code == 422


async def test_a_login_that_names_nobody_answers_like_one_that_does(client, db, tenant, tenant_headers):
    """The code, the body and the time are the same, or the answer says who has an account here."""
    await user_service.create(db, {"username": "known", "email": "known@acme.com", "password": "s3cret-password", "status": UserStatus.ACTIVE, "tenant_id": tenant.id})

    async def attempt(login):
        started = time.perf_counter()
        answer = await client.post("/api/signin", json={"login": login, "password": "not-the-password"}, headers=tenant_headers)

        return answer, time.perf_counter() - started

    known, known_took = await attempt("known@acme.com")
    nobody, nobody_took = await attempt("nobody@acme.com")

    assert known.status_code == nobody.status_code == 401
    assert known.json() == nobody.json()
    assert abs(known_took - nobody_took) < max(known_took, nobody_took)


async def test_a_purchase_of_somebody_else_does_not_exist(client, db, tenant, member, stranger_headers):
    product = await make_product(db, tenant)
    purchase = await make_purchase(db, tenant, member, product)

    assert (await client.get(f"/api/account/purchases/{purchase.id}", headers=stranger_headers)).status_code == 404


async def test_a_listing_of_the_account_never_carries_a_row_of_another(client, db, tenant, member, stranger_headers):
    product = await make_product(db, tenant)
    await make_purchase(db, tenant, member, product)

    answer = await client.get("/api/account/purchases", headers=stranger_headers)

    assert answer.json()["count"] == 0
    assert answer.json()["items"] == []


@pytest.mark.parametrize("payload", [{"role": "administrator"}, {"tenantId": 1}, {"id": 9}, {"token": "stolen"}, {"failedSignIns": 0}, {"signInBlockedUntil": None}, {"avatar": "images/user/avatar/x.webp"}])
async def test_an_account_never_names_what_only_the_engine_writes(client, member_headers, payload):
    """The schema is closed, so a field a reader has no business writing is refused and never quietly dropped."""
    answer = await client.put("/api/account/me", json=payload, headers=member_headers)

    assert answer.status_code == 422


async def test_a_reader_never_reads_what_this_account_reaches_of_somebody_else(client, member_headers):
    answer = await client.get("/api/meta/permissions", headers=member_headers)

    assert answer.json()["resources"] == []


async def test_the_map_of_who_reaches_what_is_never_answered_to_a_stranger(client):
    assert (await client.get("/api/meta/permissions")).status_code == 401


async def test_a_token_of_an_account_that_was_blocked_stops_answering(client, db, member, member_headers):
    member.status = UserStatus.BLOCKED
    await db.commit()

    assert (await client.get("/api/account/me", headers=member_headers)).status_code == 401


async def test_a_key_named_by_one_account_is_never_read_by_another(client, db, tenant, tenant_headers, member_headers, stranger_headers, monkeypatch):
    """Two clients naming a write share no namespace, or one of them reads where the other was sent to pay."""
    from services.checkout import checkout_service

    product = await make_product(db, tenant)
    body = {"successUrl": "https://acme.com/ok", "cancelUrl": "https://acme.com/no"}
    opened = []

    async def answer(session, tenant_row, user, offered, success_url, cancel_url):
        opened.append(user.id)

        return f"https://gateway.acme.com/{len(opened)}"

    monkeypatch.setattr(checkout_service, "for_product", answer)

    mine = await client.post(f"/api/commerce/products/{product.slug}/checkout", json=body, headers=member_headers | tenant_headers | {"Idempotency-Key": "shared"})
    theirs = await client.post(f"/api/commerce/products/{product.slug}/checkout", json=body, headers=stranger_headers | tenant_headers | {"Idempotency-Key": "shared"})

    assert mine.json()["url"] != theirs.json()["url"]
    assert len(opened) == 2


async def test_the_name_of_a_request_never_carries_a_second_line_into_the_log(client):
    """It reaches a log line as it was written, so anything that could forge one there is not a name."""
    from helpers.tracing import HEADER

    answer = await client.get("/api/meta/health", headers={HEADER: "edge\nFAKE"})

    assert "\n" not in answer.headers[HEADER]
    assert answer.headers[HEADER] != "edge\nFAKE"


@pytest.mark.parametrize("resource", sorted(RESOURCES))
async def test_nothing_of_the_api_answers_a_reader(client, member_headers, resource):
    """Every resource of the panel refuses an account that works nowhere, and this is the whole of them."""
    assert (await client.get(f"/api/{resource}", headers=member_headers)).status_code == 403


async def test_a_webhook_key_nobody_drew_is_not_a_way_in(client):
    assert (await client.post("/api/webhooks/not-a-key", json={"type": "TEST"})).status_code == 404


async def test_signing_in_from_a_tenant_never_reaches_the_account_of_another(client, db, tenant, tenant_headers):
    """An identity is unique inside a tenant, so the same login in another one is nobody at all."""
    from tests.factories import make_tenant

    other = await make_tenant(db, code="other", domain="other.test")
    await user_service.create(db, {"username": "shared", "email": "shared@acme.com", "password": "s3cret-password", "status": UserStatus.ACTIVE, "tenant_id": other.id})

    answer = await client.post("/api/signin", json={"login": "shared@acme.com", "password": "s3cret-password"}, headers=tenant_headers)

    assert answer.status_code == 401
    assert answer.json()["code"] == "error.invalid-credentials"


async def test_attempts_against_one_account_never_lock_out_another(client, db, tenant, tenant_headers):
    """The count is on the account being guessed at, so guessing at one is not a way to shut the door on the rest."""
    from helpers.settings import settings

    await user_service.create(db, {"username": "target", "email": "target@acme.com", "password": "the-right-one", "status": UserStatus.ACTIVE, "tenant_id": tenant.id})
    other = await user_service.create(db, {"username": "other", "email": "other@acme.com", "password": "the-right-one", "status": UserStatus.ACTIVE, "tenant_id": tenant.id})

    await asyncio.gather(*[client.post("/api/signin", json={"login": "target@acme.com", "password": "no"}, headers=tenant_headers) for _ in range(settings.security.sign_in_attempts + 2)])

    answer = await client.post("/api/signin", json={"login": "other@acme.com", "password": "the-right-one"}, headers=tenant_headers)

    assert answer.status_code == 200
    assert other.failed_sign_ins == 0


async def test_a_recovery_token_is_spent_the_first_time_it_is_used(client, db, member, tenant_headers):
    """It is one more way in, and one that stayed valid after being used is a second way in nobody asked for."""
    from sqlalchemy import select

    from models.user import User

    await client.post("/api/account/password-reset", json={"login": "reader@acme.com"}, headers=tenant_headers)
    token = await db.scalar(select(User.recovery_token).where(User.id == member.id))

    first = await client.post("/api/account/password-reset/confirm", json={"token": token, "newPassword": "the-first-new-one"}, headers=tenant_headers)
    again = await client.post("/api/account/password-reset/confirm", json={"token": token, "newPassword": "the-second-new-one"}, headers=tenant_headers)

    assert first.status_code == 204
    assert again.status_code == 422
    assert again.json()["code"] == "error.recovery-token-invalid"


async def test_the_password_the_second_attempt_asked_for_never_took(client, db, member, tenant_headers):
    """A spent token that answered an error must not have moved anything on the way to answering it."""
    from sqlalchemy import select

    from models.user import User

    await client.post("/api/account/password-reset", json={"login": "reader@acme.com"}, headers=tenant_headers)
    token = await db.scalar(select(User.recovery_token).where(User.id == member.id))

    await client.post("/api/account/password-reset/confirm", json={"token": token, "newPassword": "the-first-new-one"}, headers=tenant_headers)
    await client.post("/api/account/password-reset/confirm", json={"token": token, "newPassword": "the-second-new-one"}, headers=tenant_headers)

    assert (await client.post("/api/signin", json={"login": "reader@acme.com", "password": "the-first-new-one"}, headers=tenant_headers)).status_code == 200


async def test_a_role_that_writes_content_writes_the_html_of_the_site(site, client, db, tenant, editor_headers):
    """Whoever is given the pages is given what a browser runs on them, and that is what handing out the role costs."""
    written = "<p>By the editor</p><script>alert(1)</script>"

    created = await client.post("/api/contents", json={"title": "Terms", "tag": "terms", "content": written, "tenantId": tenant.id}, headers=editor_headers)
    drawn = await site.get("/content/terms")

    assert created.status_code == 201
    assert written in drawn.text


async def test_no_answer_ever_carries_what_is_stored_of_a_secret(client, db, tenant, admin_headers):
    """A field named innocuously is still a leak, so this looks for the values themselves and never for their names."""
    from helpers.security import encrypt
    from tests.factories import make_integration

    integration = await make_integration(db, tenant)
    integration.stripe_api_key_encrypted = encrypt("sk_live_worth_money")
    await db.commit()

    reading = [f"/api/integrations/{integration.id}", "/api/integrations", "/api/integrations/lookup", "/api/users", "/api/users/lookup"]
    stored = [integration.stripe_api_key_encrypted, "sk_live_worth_money"]

    for path in reading:
        body = (await client.get(path, headers=admin_headers)).text

        for secret in stored:
            assert secret not in body, f"{path} answered with a stored secret"

        assert "password_hash" not in body
        assert "recovery_token" not in body


@pytest.mark.parametrize("resource", ["currencies", "languages"])
async def test_deleting_a_row_something_points_at_says_so(client, db, tenant, admin_headers, resource):
    """Twenty-two keys refuse a deletion, and every one of them used to answer that a duplicate already existed."""
    from tests.factories import make_content, make_currency, make_language, make_product

    if resource == "currencies":
        held = await make_currency(db, code="gem", name="Gems")
        await make_product(db, tenant, credits_currency_id=held.id, credits=10)
    else:
        held = await make_language(db, code_iso_639_1="pt", name="Português")
        await make_content(db, language_id=held.id)

    answer = await client.delete(f"/api/{resource}/{held.id}", headers=admin_headers)

    assert answer.status_code == 409
    assert answer.json()["code"] == "error.record-still-referenced"


async def test_a_write_that_collides_still_says_it_is_a_duplicate(client, db, tenant, admin_headers):
    """The two conflicts mean different things, and one message for both is one of them lying."""
    from tests.factories import make_entitlement, make_plan, make_plan_entitlement

    plan = await make_plan(db, tenant)
    entitlement = await make_entitlement(db, tenant)
    await make_plan_entitlement(db, plan, entitlement)

    answer = await client.post("/api/plan-entitlements", json={"planId": plan.id, "entitlementId": entitlement.id}, headers=admin_headers)

    assert answer.status_code == 409
    assert answer.json()["code"] == "error.duplicated-record"


async def test_a_row_nothing_points_at_is_deleted(client, db, admin_headers):
    from tests.factories import make_currency

    free = await make_currency(db, code="gem", name="Gems")

    assert (await client.delete(f"/api/currencies/{free.id}", headers=admin_headers)).status_code == 204


async def test_a_failure_nobody_expected_says_nothing_about_the_inside(app, member_headers, monkeypatch):
    """A traceback, a query or a path in the body of a 500 is a map of the inside handed to whoever broke it."""
    from httpx import ASGITransport, AsyncClient

    from services.user import user_service

    async def explode(*args, **kwargs):
        raise RuntimeError("SELECT user.password_hash FROM user WHERE id = 1 -- /srv/fastkit/services/user.py")

    monkeypatch.setattr(user_service, "present", explode)

    # The transport of the suite hands the exception back to the caller, and a served application answers with it instead.
    async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test") as served:
        answer = await served.get("/api/account/me", headers=member_headers)

    body = answer.text

    assert answer.status_code == 500
    assert answer.json() == {"code": "error.internal", "detail": "Something went wrong on our side.", "errors": {}}
    assert "password_hash" not in body
    assert "SELECT" not in body
    assert "/srv/" not in body
    assert "Traceback" not in body


async def test_a_refused_field_names_the_field_and_never_the_column(client, member_headers):
    """What comes back is what the caller sent, in the names the caller uses, and never the shape behind them."""
    answer = await client.put("/api/account/me", json={"email": "not-an-email"}, headers=member_headers)

    assert answer.status_code == 422
    assert set(answer.json()["errors"]) == {"email"}
    assert "user." not in answer.text


async def test_an_entitlement_a_plan_lists_is_deleted_and_the_plan_stays(db, client, tenant, admin_headers):
    """A plan entitlement is an edge and never a record of its own, so it goes with either end of it."""
    from models.subscription import PlanEntitlement
    from tests.factories import make_entitlement, make_plan, make_plan_entitlement

    plan = await make_plan(db, tenant)
    entitlement = await make_entitlement(db, tenant)
    await make_plan_entitlement(db, plan, entitlement)
    await db.commit()

    assert (await client.delete(f"/api/entitlements/{entitlement.id}", headers=admin_headers)).status_code == 204
    assert await db.scalar(select(func.count()).select_from(PlanEntitlement)) == 0
    assert (await client.get(f"/api/plans/{plan.id}", headers=admin_headers)).status_code == 200


async def test_an_entitlement_a_live_subscription_granted_is_not_deleted(db, client, tenant, member, admin_headers):
    """What protects a catalogue row is what a subscription still holds of it, and never the edge a plan draws to it."""
    from services.delivery import delivery_service
    from tests.factories import make_entitlement, make_plan, make_plan_entitlement, make_subscription

    plan = await make_plan(db, tenant)
    entitlement = await make_entitlement(db, tenant)
    await make_plan_entitlement(db, plan, entitlement)
    await delivery_service.activate(db, await make_subscription(db, tenant, member, plan))
    await db.commit()

    answer = await client.delete(f"/api/entitlements/{entitlement.id}", headers=admin_headers)

    assert answer.status_code == 409
    assert answer.json()["code"] == "error.record-still-referenced"


async def test_a_login_nobody_has_costs_what_one_that_exists_costs(db, monkeypatch):
    """The answer time is the one thing a refusal cannot hide, so a login nobody has is verified against a hash of nobody rather than not verified at all."""
    weighed = []

    async def watch(raw_password, password_hash):
        weighed.append(password_hash)

        return False

    monkeypatch.setattr("services.auth.verify_password", watch)

    with pytest.raises(AuthenticationError):
        await auth_service.authenticate(db, None, "nobody-by-this-name", "whatever")

    assert weighed == [no_such_account], "a login nobody has skipped the hash, and the time alone says which accounts are here"
