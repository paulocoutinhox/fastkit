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
from helpers.security import create_token
from helpers.settings import settings
from models.integration import WebhookEvent
from models.user import User, UserAddress
from services.user import user_service
from tests.conftest import opened, token_in
from tests.factories import make_integration, make_plan, make_subscription, make_tenant, save

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


async def test_somebody_signs_up_and_lands_signed_in(site, tenant, monkeypatch):
    """Where the environment asks for no confirmation, signing up is the whole of it and the session starts there."""
    monkeypatch.setattr(settings, "confirm_sign_up", False)

    token = await opened(site, "/account/signup")

    answer = await site.post("/account/signup", data={"csrf_token": token, "first_name": "Ada", "last_name": "Lovelace", "email": "ada@acme.com", "password": "a-strong-secret"}, follow_redirects=False)

    assert answer.status_code == 303
    assert (await site.get("/account")).status_code == 200


async def test_somebody_signing_up_where_the_address_answers_first_gets_no_session(site, tenant):
    """The account is created and it is waiting, so the page says where to look and nothing is opened here."""
    token = await opened(site, "/account/signup")

    answer = await site.post("/account/signup", data={"csrf_token": token, "first_name": "Ada", "last_name": "Lovelace", "email": "ada@acme.com", "password": "a-strong-secret"}, follow_redirects=False)

    assert answer.status_code == 303
    assert answer.headers["location"].endswith("/account/login")
    assert site.cookies.get(settings.site.session_cookie) is None


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
    assert answer.headers["location"] == "/account/login?next=%2Faccount"


async def test_a_recovery_link_that_opens_nothing_sends_the_person_to_ask_for_another(site):
    """A form under a spent or expired link can never succeed, so it is never drawn."""
    answer = await site.get("/account/reset-password/made-up", follow_redirects=False)

    assert answer.headers["location"] == "/account/password-recovery"
    assert "invalid" in (await site.get("/account/password-recovery")).text.lower()


async def test_a_recovery_link_spent_while_the_form_was_open_sends_the_person_to_ask_again(site, db, member):
    from services.auth import auth_service

    await auth_service.start_password_reset(db, brand.of(member.tenant), member.email)
    await db.refresh(member)

    held = member.recovery_token
    token = await opened(site, f"/account/reset-password/{held}")

    await auth_service.confirm_password_reset(db, member.tenant_id, held, "spent-somewhere-else")
    answer = await site.post(f"/account/reset-password/{held}", data={"csrf_token": token, "new_password": "a-brand-new-secret"}, follow_redirects=False)

    assert answer.headers["location"] == "/account/password-recovery"


async def test_a_password_the_rules_refuse_draws_the_form_again(site, db, member):
    from services.auth import auth_service

    await auth_service.start_password_reset(db, brand.of(member.tenant), member.email)
    await db.refresh(member)

    token = await opened(site, f"/account/reset-password/{member.recovery_token}")
    answer = await site.post(f"/account/reset-password/{member.recovery_token}", data={"csrf_token": token, "new_password": "short"})

    assert answer.status_code == 422


async def test_where_the_person_was_going_crosses_the_whole_recovery(site, db, member, monkeypatch):
    """The recovery is a wait the browser never crosses, so the destination rides the letter and then the login."""
    from services.email import email_service

    letters = []

    async def written(*arguments, **context):
        letters.append(context)

    monkeypatch.setattr(email_service, "to_user", written)

    login = (await site.get("/account/login?next=%2Faccount%2Fcredits")).text
    assert "/account/password-recovery?next=/account/credits" in login

    token = await opened(site, "/account/password-recovery?next=%2Faccount%2Fcredits")
    await site.post("/account/password-recovery", data={"csrf_token": token, "login": member.email, "next": "/account/credits", "captcha_answer": "", "captcha_token": ""})
    await db.refresh(member)

    link = letters[0]["link"]
    assert link.endswith(f"/account/reset-password/{member.recovery_token}?next=%2Faccount%2Fcredits")

    path = link.split(member.tenant.domain, 1)[1]
    token = await opened(site, path)
    answer = await site.post(f"/account/reset-password/{member.recovery_token}", data={"csrf_token": token, "new_password": "a-brand-new-secret", "next": "/account/credits"}, follow_redirects=False)

    assert answer.headers["location"] == "/account/login?next=%2Faccount%2Fcredits"


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


async def test_the_pages_are_read_in_the_language_chosen_on_the_site_and_not_in_the_one_of_the_account(signed_in, db, member):
    """The language of an account is the one its messages are written in, and the reader chooses the one the pages are read in."""
    from tests.factories import make_language

    portuguese = await make_language(db, name="Português", native_name="Português", code_iso_639_1="pt", code_iso_language="pt-br")
    member.language_id = portuguese.id
    await db.commit()

    signed_in.cookies.set(settings.site.language_cookie, "en")

    assert "Plans" in (await signed_in.get("/plans")).text


async def test_choosing_a_language_on_the_site_never_touches_the_language_of_the_account(signed_in, db, member):
    """The flags turn the text of the pages, and the messages of the account stay in the language its profile chose."""
    from tests.factories import make_language

    english = await make_language(db)
    await make_language(db, name="Português", native_name="Português", code_iso_639_1="pt", code_iso_language="pt-br")
    member.language_id = english.id
    await db.commit()

    token = await opened(signed_in, "/plans")

    await signed_in.post("/language", data={"csrf_token": token, "language": "pt", "next": "/plans"})
    await db.refresh(member)

    assert member.language_id == english.id
    assert "Planos" in (await signed_in.get("/plans")).text


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


async def test_the_language_of_the_messages_is_saved_on_the_account_and_the_page_stays_in_its_own(signed_in, db, member):
    """The profile chooses what the account receives its mail in, so the page that saved it keeps answering in the language it is read in."""
    from tests.factories import make_language

    portuguese = await make_language(db, name="Português", native_name="Português", code_iso_639_1="pt", code_iso_language="pt-br")

    token = await opened(signed_in, "/account/profile")
    answer = await signed_in.post("/account/profile", data={"csrf_token": token, "language_id": str(portuguese.id)}, follow_redirects=False)
    await db.refresh(member)

    assert member.language_id == portuguese.id
    assert settings.site.language_cookie not in answer.headers.get("set-cookie", "")
    assert "Your profile was saved." in (await signed_in.get("/account/profile")).text


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


async def test_a_language_nobody_offers_is_not_a_choice_of_the_account(signed_in, db):
    """The form draws only what the instance offers, and a request written by hand is refused by the same rule the API answers by."""
    from tests.factories import make_language

    german = await make_language(db, name="Deutsch", native_name="Deutsch", code_iso_639_1="de", code_iso_language="de-de")
    token = await opened(signed_in, "/account/profile")

    assert "Deutsch" not in (await signed_in.get("/account/profile")).text

    answer = await signed_in.post("/account/profile", data={"csrf_token": token, "language_id": str(german.id)})

    assert answer.status_code == 422
    assert "This language is not offered here." in answer.text


async def test_an_account_known_only_by_its_document_is_shown_by_it(signed_in, db, member):
    """The line under the name read the email, the username and the phone, so an account whose only identity is its document drew an empty line."""
    from services.user import user_service

    await user_service.update(db, member.id, {"document": "52998224725", "email": None, "username": None, "mobile_phone": None})

    assert "52998224725" in (await signed_in.get("/account")).text


async def test_the_profile_draws_every_field_an_account_writes_about_itself(signed_in):
    """The site, the API and the panel offer one set of fields, so the form is read against the payload and never against a list of its own."""
    from schemas.auth import AccountUpdateRequest

    page = (await signed_in.get("/account/profile")).text

    assert [name for name in AccountUpdateRequest.model_fields if f'name="{name}"' not in page] == []


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


async def test_turning_the_page_keeps_everything_else_the_address_was_carrying(signed_in, db, tenant, member):
    """The piece is shared by every paginated page, so a link that writes the page number alone drops the filter that narrowed the listing."""
    plan = await make_plan(db, tenant)
    integration = await make_integration(db, tenant)
    subscription = await make_subscription(db, tenant, member, plan, integration_id=integration.id)

    for position in range(settings.site.page_size + 1):
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

    drawn = (await signed_in.get(f"/account/subscriptions/{subscription.id}?kind=renewal")).text

    assert "kind=renewal&amp;page=2" in drawn


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


async def test_the_link_in_the_message_asks_and_only_the_answer_opens_the_account(site, db, tenant):
    """A mail client and the scanner in front of it open a link on their own, so opening it changes nothing and the answer sent from the page is what puts the person inside."""
    token = await opened(site, "/account/signup")

    await site.post("/account/signup", data={"csrf_token": token, "first_name": "Ada", "email": "ada@acme.com", "password": "a-strong-secret"}, follow_redirects=False)

    account = await db.scalar(select(User).where(User.email == "ada@acme.com"))
    link = f"/account/confirm/{account.confirmation_token}"
    asked = await site.get(link)

    await db.refresh(account)

    assert asked.status_code == 200
    assert account.status == UserStatus.PENDING

    answered = await site.post(link, data={"csrf_token": token_in(asked.text)}, follow_redirects=False)

    assert answered.status_code == 303
    assert answered.headers["location"].endswith("/account")
    assert (await site.get("/account")).status_code == 200


async def test_an_answer_sent_after_the_link_stopped_opening_anything_says_so(site, db, tenant):
    """The page was drawn while the letter was still the last one, and a newer letter asked for in between is the one that opens the account now."""
    token = await opened(site, "/account/signup")

    await site.post("/account/signup", data={"csrf_token": token, "first_name": "Ada", "email": "ada@acme.com", "password": "a-strong-secret"}, follow_redirects=False)

    account = await db.scalar(select(User).where(User.email == "ada@acme.com"))
    link = f"/account/confirm/{account.confirmation_token}"
    asked = await site.get(link)

    account.confirmation_token = "the-newer-letter"
    await db.commit()

    answered = await site.post(link, data={"csrf_token": token_in(asked.text)}, follow_redirects=False)

    assert answered.status_code == 303
    assert answered.headers["location"].endswith("/account/login")
    assert site.cookies.get(settings.site.session_cookie) is None


async def test_a_link_that_opens_nothing_says_so_on_the_page_it_lands_on(site, tenant):
    answered = await site.get("/account/confirm/not-a-real-token", follow_redirects=False)

    assert answered.status_code == 303
    assert answered.headers["location"].endswith("/account/login")
    assert site.cookies.get(settings.site.session_cookie) is None


async def test_the_page_that_asks_for_the_message_again_says_nothing_about_the_account(site, db, tenant):
    token = await opened(site, "/account/confirmation")

    await site.post("/account/signup", data={"csrf_token": await opened(site, "/account/signup"), "first_name": "Ada", "email": "ada@acme.com", "password": "a-strong-secret"}, follow_redirects=False)

    waiting = await site.post("/account/confirmation", data={"csrf_token": token, "login": "ada@acme.com"}, follow_redirects=False)
    unknown = await site.post("/account/confirmation", data={"csrf_token": token, "login": "nobody@acme.com"}, follow_redirects=False)

    assert waiting.status_code == unknown.status_code == 303
    assert waiting.headers["location"] == unknown.headers["location"]


async def test_the_page_that_asks_for_the_message_again_draws_itself_when_it_refuses(site, tenant):
    token = await opened(site, "/account/confirmation")

    answer = await site.post("/account/confirmation", data={"csrf_token": token, "login": "no"})

    assert answer.status_code == 422


async def test_a_link_of_another_brand_opens_nothing_here(site, db, tenant):
    """An account is an account of one brand, so its letter followed on another brand's site neither opens it nor signs anybody in there."""
    other = await make_tenant(db, code="rival", domain="rival.acme.com")
    waiting = await user_service.create(db, {"email": "rival@acme.com", "password": "s3cret-password", "tenant_id": other.id, "status": UserStatus.PENDING})
    waiting.confirmation_token = "a-letter-of-the-rival"
    await db.commit()

    asked = await site.get("/account/confirm/a-letter-of-the-rival", follow_redirects=False)

    assert asked.headers["location"] == "/account/login"
    assert settings.site.session_cookie not in asked.cookies


async def test_a_session_of_another_brand_is_nobody_here(site, db, tenant):
    """A session cookie is only ever minted on the site of the account's own brand, and one carried anywhere else signs nobody in."""
    other = await make_tenant(db, code="rival", domain="rival.acme.com")
    stranger = await user_service.create(db, {"email": "rival@acme.com", "password": "s3cret-password", "tenant_id": other.id, "status": UserStatus.ACTIVE})

    site.cookies.set(settings.site.session_cookie, create_token(stranger.token, stranger.role, stranger.session_epoch), domain=tenant.domain, path="/")

    assert (await site.get("/account", follow_redirects=False)).status_code == 303


async def test_a_login_drawn_again_after_a_refusal_keeps_where_the_person_was_going_in_every_other_form(site):
    """The flags, the theme and the cookie notice send the person back to this page, and the address of the refused post carries no destination."""
    wanted = "/account/login?next=%2Faccount%2Faddress"
    token = await opened(site, wanted)

    refused = await site.post("/account/login", data={"csrf_token": token, "login": "nobody", "password": "wrong-password", "next": "/account/address"}, headers={"referer": f"http://{site.base_url.host}{wanted}"})

    assert refused.status_code == 422
    assert 'name="next" value="/account/login"' not in refused.text
    assert f'value="{wanted}"' in refused.text


async def test_the_site_asks_to_take_a_new_address_and_the_profile_says_which_one_waits(signed_in, db, member):
    """A letter about a new address asks to use it, and not to open an account that is already open."""
    from models.user import User
    from services.auth import auth_service

    await auth_service.settle_account(db, member, {"email": "new@acme.com"})
    token = await db.scalar(select(User.confirmation_token).where(User.id == member.id))

    question = await signed_in.get(f"/account/confirm/{token}")
    profile = await signed_in.get("/account/profile")

    assert "Use this address" in question.text
    assert "new@acme.com" in profile.text


async def test_answering_a_new_address_writes_it_and_opens_no_session(site, db, member):
    """The letter proves the mailbox and not the account, and a stranger holding a letter sent to a mistyped address must not walk into it."""
    from services.auth import auth_service

    await auth_service.settle_account(db, member, {"email": "mistyped@acme.com"})
    link = f"/account/confirm/{await db.scalar(select(User.confirmation_token).where(User.id == member.id))}"
    asked = await site.get(link)

    answered = await site.post(link, data={"csrf_token": token_in(asked.text)}, follow_redirects=False)

    assert answered.status_code == 303
    assert site.cookies.get(settings.site.session_cookie) is None
    assert await db.scalar(select(User.email).where(User.id == member.id).execution_options(populate_existing=True)) == "mistyped@acme.com"
