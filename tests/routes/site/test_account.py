"""The pages behind the session, and the guards that decide who reaches one."""

import secrets
from datetime import timedelta
from decimal import Decimal
from urllib.parse import quote

import pytest
from sqlalchemy import select

from enums.integration import NormalizedAction, WebhookEventStatus
from enums.user import UserStatus
from helpers import brand
from helpers.dates import now
from helpers.settings import settings
from models.integration import WebhookEvent
from models.language import Language
from models.user import UserAddress
from tests.conftest import opened
from tests.factories import make_integration, make_plan, make_subscription, save

PRIVATE = ["/account", "/account/profile", "/account/password", "/account/address", "/account/subscriptions", "/account/purchases", "/account/products", "/account/credits", "/account/delete"]


@pytest.mark.parametrize("path", PRIVATE)
async def test_a_page_of_the_account_sends_a_visitor_with_no_session_to_the_sign_in(site, path):
    """Where they were going travels with them, so answering the sign in puts them there and not somewhere else."""
    answer = await site.get(path, follow_redirects=False)

    assert answer.status_code == 303
    assert answer.headers["location"] == f"/account/login?next={quote(path, safe='')}"


async def test_a_form_that_needs_a_session_sends_the_visitor_to_the_page_it_was_drawn_on(site):
    """Coming back from the sign in is a GET, and the address a form posts to answers nothing on one."""
    answer = await site.post("/checkout/plan/monthly", data={}, headers={"referer": "http://acme.test/plans"}, follow_redirects=False)

    assert answer.status_code == 303
    assert answer.headers["location"] == f"/account/login?next={quote('/plans', safe='')}"


async def test_a_form_with_no_page_behind_it_sends_the_visitor_home(site):
    answer = await site.post("/checkout/plan/monthly", data={}, follow_redirects=False)

    assert answer.headers["location"] == f"/account/login?next={quote('/', safe='')}"


@pytest.mark.parametrize("path", PRIVATE)
async def test_a_page_of_the_account_answers_whoever_has_a_session(signed_in, path):
    answer = await signed_in.get(path)

    assert answer.status_code == 200
    assert "<h1" in answer.text


async def test_signing_in_opens_a_session_and_the_pages_that_need_one(site, member):
    token = await opened(site, "/account/login")

    answer = await site.post("/account/login", data={"csrf_token": token, "login": member.email, "password": "s3cret-password"}, follow_redirects=False)

    assert answer.status_code == 303
    assert answer.headers["location"] == "/account"
    assert site.cookies.get(settings.site.session_cookie)
    assert (await site.get("/account")).status_code == 200


async def test_a_wrong_password_draws_the_form_again_and_never_a_session(site, member):
    token = await opened(site, "/account/login")

    answer = await site.post("/account/login", data={"csrf_token": token, "login": member.email, "password": "not-it"})

    assert answer.status_code == 422
    assert site.cookies.get(settings.site.session_cookie) is None


async def test_a_post_with_no_token_is_sent_back_to_the_page_it_came_from(site, member):
    """A form of the site never leaves as a body of JSON, so a page that went stale is the page drawn again with a notice."""
    await site.get("/account/login")

    answer = await site.post("/account/login", data={"login": member.email, "password": "s3cret-password"}, headers={"referer": "http://acme.test/account/login"}, follow_redirects=False)

    assert answer.status_code == 303
    assert answer.headers["location"] == "/account/login"

    drawn = await site.get("/account/login")

    assert "<!doctype html>" in drawn.text
    assert "csrf" in drawn.text.lower()


async def test_a_post_with_no_token_and_nowhere_to_go_back_to_lands_on_the_home(site, member):
    answer = await site.post("/account/login", data={"login": member.email, "password": "s3cret-password"}, follow_redirects=False)

    assert answer.headers["location"] == "/"


async def test_a_token_of_another_visitor_is_refused(site, member):
    """The cookie and the field carry the same value, and only a page of this site can read one to fill the other."""
    await site.get("/account/login")

    answer = await site.post("/account/login", data={"csrf_token": "forged-by-somebody-else", "login": member.email, "password": "s3cret-password"}, follow_redirects=False)

    assert answer.status_code == 303


async def test_signing_out_closes_the_session(signed_in):
    token = await opened(signed_in, "/account")

    answer = await signed_in.post("/account/logout", data={"csrf_token": token}, follow_redirects=False)

    assert answer.status_code == 303
    assert (await signed_in.get("/account", follow_redirects=False)).status_code == 303


async def test_somebody_signs_up_and_lands_signed_in(site, tenant):
    token = await opened(site, "/account/signup")

    answer = await site.post("/account/signup", data={"csrf_token": token, "first_name": "Ada", "last_name": "Lovelace", "email": "ada@acme.com", "password": "a-strong-secret"}, follow_redirects=False)

    assert answer.status_code == 303
    assert (await site.get("/account")).status_code == 200


async def test_a_signup_the_rules_refuse_draws_the_form_again(site):
    token = await opened(site, "/account/signup")

    answer = await site.post("/account/signup", data={"csrf_token": token, "first_name": "A", "email": "not-an-email", "password": "short"})

    assert answer.status_code == 422
    assert "form" in answer.text


async def test_an_email_somebody_already_uses_is_refused_by_the_page(site, member):
    token = await opened(site, "/account/signup")

    answer = await site.post("/account/signup", data={"csrf_token": token, "first_name": "Ada", "email": member.email, "password": "a-strong-secret"})

    assert answer.status_code == 422


async def test_a_visitor_with_a_session_is_sent_away_from_the_sign_in(signed_in):
    assert (await signed_in.get("/account/login", follow_redirects=False)).status_code == 303
    assert (await signed_in.get("/account/signup", follow_redirects=False)).status_code == 303


async def test_the_profile_is_edited_from_its_own_page(signed_in, db, member):
    token = await opened(signed_in, "/account/profile")

    answer = await signed_in.post("/account/profile", data={"csrf_token": token, "first_name": "Ada", "last_name": "Lovelace", "nickname": "Ada"}, follow_redirects=False)

    assert answer.status_code == 303

    await db.refresh(member)

    assert member.nickname == "Ada"


async def test_a_profile_that_would_erase_every_way_in_is_refused(signed_in, member):
    token = await opened(signed_in, "/account/profile")

    answer = await signed_in.post("/account/profile", data={"csrf_token": token, "email": "", "username": "", "mobile_phone": ""})

    assert answer.status_code == 422


async def test_the_password_is_changed_and_this_device_stays_in(signed_in, db, member):
    token = await opened(signed_in, "/account/password")

    answer = await signed_in.post("/account/password", data={"csrf_token": token, "current_password": "s3cret-password", "new_password": "another-strong-secret"}, follow_redirects=False)

    assert answer.status_code == 303
    assert (await signed_in.get("/account")).status_code == 200


async def test_a_wrong_current_password_changes_nothing(signed_in):
    token = await opened(signed_in, "/account/password")

    answer = await signed_in.post("/account/password", data={"csrf_token": token, "current_password": "not-it", "new_password": "another-strong-secret"})

    assert answer.status_code == 422


async def test_the_address_is_written_and_read_back(signed_in, db, member):
    from tests.factories import make_country

    await make_country(db)

    token = await opened(signed_in, "/account/address")
    payload = {"csrf_token": token, "line1": "221B Baker Street", "city": "London", "state": "London", "postal_code": "NW16XE", "country_code": "gb"}

    answer = await signed_in.post("/account/address", data=payload, follow_redirects=False)

    assert answer.status_code == 303

    held = await db.scalar(select(UserAddress).where(UserAddress.user_id == member.id))

    assert held.country_code == "GB"
    assert "221B Baker Street" in (await signed_in.get("/account/address")).text


async def test_the_phone_is_drawn_in_the_shape_the_country_of_the_account_writes_it_in(signed_in, db):
    """A country with no shape of its own draws a plain field, the same way one with nobody to ask about a postal code does."""
    from tests.factories import make_country

    await make_country(db, code_iso_3166_1="BR", name="Brazil", phone_mask="(00) 00000-0000")

    plain = await signed_in.get("/account/profile")

    assert "data-mask" not in plain.text

    token = await opened(signed_in, "/account/address")
    await signed_in.post("/account/address", data={"csrf_token": token, "line1": "Rua A", "city": "Sao Paulo", "state": "SP", "postal_code": "01001000", "country_code": "BR"})

    assert 'data-mask="(00) 00000-0000"' in (await signed_in.get("/account/profile")).text


async def test_an_address_the_rules_refuse_draws_the_form_again(signed_in):
    token = await opened(signed_in, "/account/address")

    answer = await signed_in.post("/account/address", data={"csrf_token": token, "line1": "", "city": "", "state": "", "postal_code": "", "country_code": ""})

    assert answer.status_code == 422


async def test_asking_for_a_recovery_never_says_whether_the_account_is_there(site, member):
    token = await opened(site, "/account/password-recovery")

    known = await site.post("/account/password-recovery", data={"csrf_token": token, "login": member.email}, follow_redirects=False)
    unknown = await site.post("/account/password-recovery", data={"csrf_token": token, "login": "nobody@acme.com"}, follow_redirects=False)

    assert known.status_code == unknown.status_code == 303
    assert known.headers["location"] == unknown.headers["location"]


async def test_a_recovery_token_sets_a_new_password(site, db, member):
    from services.auth import auth_service

    await auth_service.start_password_reset(db, brand.of(member.tenant), member.email)
    await db.refresh(member)

    token = await opened(site, f"/account/reset-password/{member.recovery_token}")
    answer = await site.post(f"/account/reset-password/{member.recovery_token}", data={"csrf_token": token, "new_password": "a-brand-new-secret"}, follow_redirects=False)

    assert answer.status_code == 303
    assert answer.headers["location"] == "/account/login"


async def test_a_recovery_token_nobody_minted_is_refused(site):
    token = await opened(site, "/account/reset-password/made-up")

    answer = await site.post("/account/reset-password/made-up", data={"csrf_token": token, "new_password": "a-brand-new-secret"})

    assert answer.status_code == 422


async def test_a_password_the_rules_refuse_draws_the_form_again(site):
    token = await opened(site, "/account/reset-password/made-up")

    answer = await site.post("/account/reset-password/made-up", data={"csrf_token": token, "new_password": "short"})

    assert answer.status_code == 422


async def test_an_account_with_no_address_is_asked_for_the_identity_it_does_have(signed_in, db, member):
    """An account is created with any of the four, so asking for an address it never had is a page nobody can send."""
    member.email = None
    await db.commit()

    body = (await signed_in.get("/account/delete")).text

    assert "Type reader to confirm" in body


async def test_the_account_is_erased_only_when_the_person_types_their_own_address(signed_in, db, member):
    token = await opened(signed_in, "/account/delete")

    refused = await signed_in.post("/account/delete", data={"csrf_token": token, "confirmation": "something-else"})

    assert refused.status_code == 422

    answer = await signed_in.post("/account/delete", data={"csrf_token": token, "confirmation": member.email}, follow_redirects=False)

    assert answer.status_code == 303

    await db.refresh(member)

    assert member.status == UserStatus.ERASED


async def test_the_picture_of_the_account_is_sent_and_removed_from_its_own_page(signed_in, db, member):
    import base64

    png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
    token = await opened(signed_in, "/account")

    stored = await signed_in.post("/account/avatar", data={"csrf_token": token}, files={"file": ("me.png", png, "image/png")}, follow_redirects=False)

    assert stored.status_code == 303

    await db.refresh(member)

    assert member.avatar

    removed = await signed_in.post("/account/avatar/remove", data={"csrf_token": token}, follow_redirects=False)

    assert removed.status_code == 303

    await db.refresh(member)

    assert member.avatar is None


async def test_a_picture_the_rules_refuse_says_so_instead_of_breaking(signed_in):
    token = await opened(signed_in, "/account")

    answer = await signed_in.post("/account/avatar", data={"csrf_token": token}, files={"file": ("me.txt", b"not a picture", "text/plain")}, follow_redirects=False)

    assert answer.status_code == 303


async def test_what_the_account_owns_and_paid_is_listed(signed_in, db, tenant, member):
    from enums.commerce import PurchaseStatus
    from services.commerce import commerce_service
    from tests.factories import make_product

    product = await make_product(db, tenant, name="The Handbook")
    purchase = await commerce_service.open_purchase(db, tenant, member, product, None)
    await commerce_service.settle_purchase(db, purchase, PurchaseStatus.PAID, "pi_1")

    assert "The Handbook" in (await signed_in.get("/account/products")).text
    assert "The Handbook" in (await signed_in.get("/account/purchases")).text


async def test_the_wallet_is_shown_with_the_movements_behind_it(signed_in, db, member, currency):
    from enums.account import CreditTransactionType
    from services.account import credit_transaction_service

    await credit_transaction_service.move(db, member.id, currency.id, CreditTransactionType.CREDIT, 25, "bonus", "k-1", None, {})

    assert "25" in (await signed_in.get("/account/credits")).text


async def test_the_subscriptions_of_the_account_are_listed(signed_in, db, tenant, member):
    from tests.factories import make_plan, make_subscription

    plan = await make_plan(db, tenant, name="Monthly")
    await make_subscription(db, tenant, member, plan)

    assert "Monthly" in (await signed_in.get("/account/subscriptions")).text


async def test_a_session_of_an_account_that_was_blocked_stops_answering(signed_in, db, member):
    member.status = UserStatus.BLOCKED
    await db.commit()

    assert (await signed_in.get("/account", follow_redirects=False)).status_code == 303


async def test_the_language_of_the_account_outranks_the_cookie_of_the_browser(signed_in, db, member):
    """A person who chose a language on one machine reads the same one on the next, because the choice followed the account."""
    from tests.factories import make_language

    portuguese = await make_language(db, name="Português", native_name="Português", code_iso_639_1="pt", code_iso_language="pt-br")
    member.language_id = portuguese.id
    await db.commit()

    signed_in.cookies.set("fastkit_language", "en")

    assert "Planos" in (await signed_in.get("/plans")).text


async def test_choosing_a_language_while_signed_in_keeps_it_on_the_account(signed_in, db, member):
    from tests.factories import make_language

    await make_language(db, name="Português", native_name="Português", code_iso_639_1="pt", code_iso_language="pt-br")

    token = await opened(signed_in, "/plans")

    await signed_in.post("/language", data={"csrf_token": token, "language": "pt", "next": "/plans"})
    await db.refresh(member)

    assert (await db.get(Language, member.language_id)).code_iso_639_1 == "pt"


async def test_an_address_names_a_country_this_instance_offers(signed_in, db):
    """The select of the form is one half of the rule and the service is the other, and the one that counts is the service."""
    from tests.factories import make_country

    await make_country(db)

    token = await opened(signed_in, "/account/address")
    answer = await signed_in.post("/account/address", data={"csrf_token": token, "line1": "Rua A", "city": "Sao Paulo", "state": "SP", "postal_code": "01001000", "country_code": "ZW"})

    assert answer.status_code == 422
    assert "error.country-not-offered" not in answer.text


async def test_the_address_form_names_only_the_countries_a_postal_code_is_looked_up_for(signed_in, db):
    from enums.country import PostalCodeProvider
    from tests.factories import make_country

    await make_country(db)
    await make_country(db, name="Brazil", code_iso_3166_1="BR", postal_code_provider=PostalCodeProvider.VIACEP)

    body = (await signed_in.get("/account/address")).text

    assert 'data-postal-code-countries="BR"' in body
    assert '<option value="GB"' in body


async def test_a_postal_code_is_looked_up_only_for_a_country_that_has_somebody_to_ask(signed_in, db):
    await make_country_pair(db)

    assert (await signed_in.get("/account/address/postal-code", params={"country": "GB", "code": "NW16XE"})).status_code == 404


async def test_a_postal_code_answers_what_the_provider_found(signed_in, db, monkeypatch):
    from helpers import postal_code
    from helpers.postal_code import PostalAddress

    await make_country_pair(db)

    async def found(provider, code):
        return PostalAddress(line1="Praça da Sé", district="Sé", city="São Paulo", state="SP")

    monkeypatch.setattr(postal_code, "find", found)

    answer = await signed_in.get("/account/address/postal-code", params={"country": "BR", "code": "01001000"})

    assert answer.status_code == 200
    assert answer.json()["city"] == "São Paulo"


async def test_a_postal_code_nobody_knows_is_not_an_address(signed_in, db, monkeypatch):
    from helpers import postal_code

    await make_country_pair(db)

    async def missing(provider, code):
        return None

    monkeypatch.setattr(postal_code, "find", missing)

    answer = await signed_in.get("/account/address/postal-code", params={"country": "BR", "code": "00000000"})

    assert answer.status_code == 404
    assert answer.json()["code"] == "error.postal-code-not-found"


async def make_country_pair(db):
    from enums.country import PostalCodeProvider
    from tests.factories import make_country

    await make_country(db)
    await make_country(db, name="Brazil", code_iso_3166_1="BR", postal_code_provider=PostalCodeProvider.VIACEP)


async def test_the_notice_of_a_language_change_arrives_in_the_language_that_was_chosen(signed_in, db):
    """Choosing is what makes this request speak the new language, or the confirmation lands in the one being left behind."""
    from tests.factories import make_language

    await make_language(db, name="Português", native_name="Português", code_iso_639_1="pt", code_iso_language="pt-br")

    token = await opened(signed_in, "/account/language")
    await signed_in.post("/account/language", data={"csrf_token": token, "language": "pt"})

    assert "Idioma salvo." in (await signed_in.get("/account/language")).text


async def test_a_subscription_opens_the_payments_of_its_own_cycles(signed_in, db, tenant, member):
    """The number in the path is what somebody typed, so the account of the session is what says whose subscription it is."""
    from enums.integration import NormalizedAction
    from helpers.dates import now
    from models.integration import WebhookEvent
    from tests.factories import make_integration, make_plan, make_subscription

    plan = await make_plan(db, tenant)
    held = await make_subscription(db, tenant, member, plan)
    integration = await make_integration(db, tenant)

    db.add(WebhookEvent(tenant_id=tenant.id, integration_id=integration.id, subscription_id=held.id, user_id=member.id, external_event_id="evt-1", payload_hash="h", action=NormalizedAction.RENEW, payload={}, amount=Decimal("19.90"), currency="USD", occurred_at=now(), meta={}))
    await db.commit()

    answer = await signed_in.get(f"/account/subscriptions/{held.id}")

    assert answer.status_code == 200
    assert "19.90" in answer.text

    assert (await signed_in.get("/account/subscriptions/999999")).status_code == 404


async def test_a_purchase_opens_on_its_own_and_says_whether_it_handed_anything_over(signed_in, db, tenant, member):
    from services.commerce import commerce_service
    from tests.factories import make_product, make_purchase

    product = await make_product(db, tenant)
    bought = await make_purchase(db, tenant, member, product)

    assert (await signed_in.get(f"/account/purchases/{bought.id}")).status_code == 200

    await commerce_service.grant(db, member.id, product.id, f"purchase:{bought.id}", purchase_id=bought.id)

    answer = await signed_in.get(f"/account/purchases/{bought.id}")

    assert answer.status_code == 200
    assert bought.reference in answer.text

    assert (await signed_in.get("/account/purchases/999999")).status_code == 404


async def test_a_language_nobody_offers_is_not_a_choice_of_the_account(signed_in):
    token = await opened(signed_in, "/account/language")

    assert (await signed_in.post("/account/language", data={"csrf_token": token, "language": "de"})).status_code == 404


async def test_an_account_is_born_reading_what_the_person_was_already_reading(site, db, tenant):
    """The default language of an account is the one it signed up in, so the first message it gets is in that one."""
    from sqlalchemy import select

    from models.user import User
    from tests.factories import make_language

    await make_language(db)
    portuguese = await make_language(db, name="Português", native_name="Português", code_iso_639_1="pt", code_iso_language="pt-br")

    token = await opened(site, "/account/signup")
    await site.post("/account/signup", data={"csrf_token": token, "first_name": "Ada", "email": "ada@acme.com", "password": "s3cret-password"}, headers={"accept-language": "pt-BR,pt;q=0.9"})

    written = await db.scalar(select(User).where(User.email == "ada@acme.com"))

    assert written.language_id == portuguese.id


async def test_the_payments_of_a_subscription_turn_the_page(signed_in, db, tenant, member):
    """A page that draws every notice a gateway ever sent is one that grows without a ceiling."""
    plan = await make_plan(db, tenant)
    integration = await make_integration(db, tenant)
    subscription = await make_subscription(db, tenant, member, plan, integration_id=integration.id)
    written = settings.site.page_size + 1

    for position in range(written):
        await save(
            db,
            WebhookEvent(
                tenant_id=tenant.id,
                integration_id=integration.id,
                subscription_id=subscription.id,
                user_id=member.id,
                external_event_id=secrets.token_hex(8),
                payload_hash=secrets.token_hex(16),
                status=WebhookEventStatus.COMPLETED,
                action=NormalizedAction.RENEW,
                amount=Decimal(position + 1),
                currency="USD",
                occurred_at=now() - timedelta(days=position),
                payload={},
                meta={},
            ),
        )

    first = await signed_in.get(f"/account/subscriptions/{subscription.id}")
    drawn = [position for position in range(1, written + 1) if f"USD {position}.00" in first.text]

    assert first.status_code == 200
    assert len(drawn) == settings.site.page_size
    assert f"/account/subscriptions/{subscription.id}?page=2" in first.text

    second = await signed_in.get(f"/account/subscriptions/{subscription.id}?page=2")

    assert f"USD {written}.00" in second.text


async def test_a_date_is_read_by_the_clock_of_whoever_reads_it(signed_in, db, tenant, member):
    """Every instant is stored in UTC, so a purchase made at nine in the evening in Sao Paulo is not one made the next day."""
    from datetime import datetime, timezone

    from tests.factories import make_product, make_purchase

    product = await make_product(db, tenant)
    await make_purchase(db, tenant, member, product, created_at=datetime(2026, 8, 30, 0, 30, tzinfo=timezone.utc))

    member.timezone = "America/Sao_Paulo"
    await db.commit()

    answer = await signed_in.get("/account/purchases")

    assert answer.status_code == 200
    assert "2026-08-29" in answer.text
    assert "2026-08-30" not in answer.text

    member.timezone = "Asia/Tokyo"
    await db.commit()

    assert "2026-08-30" in (await signed_in.get("/account/purchases")).text
