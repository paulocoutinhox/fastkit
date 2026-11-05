"""A wrong password is counted on the account, because the account is what is being guessed at."""

from datetime import timedelta

import pytest
from sqlalchemy import update

from enums.user_role import UserRole
from enums.user_status import UserStatus
from helpers.authentication_error import AuthenticationError
from helpers.dates import now
from helpers.settings import settings
from models.user import User
from services.auth_service import auth_service
from services.user_service import user_service


async def make_target(db, tenant):
    return await user_service.create(db, {"username": "target", "email": "target@acme.com", "password": "the-right-one", "role": UserRole.NORMAL, "status": UserStatus.ACTIVE, "tenant_id": tenant.id})


async def wrong(client, tenant_headers, login, times):
    for _ in range(times):
        await client.post("/api/signin", json={"login": login, "password": "not-the-password"}, headers=tenant_headers)


async def test_the_account_stops_answering_after_enough_wrong_passwords(client, db, tenant, tenant_headers):
    """Nothing else counts this: the limiter counts addresses, and it counts them in the memory of one process."""
    user = await make_target(db, tenant)

    await wrong(client, tenant_headers, "target@acme.com", settings.security.sign_in_attempts)
    await db.refresh(user)

    assert user.failed_sign_ins == settings.security.sign_in_attempts
    assert user.sign_in_blocked_until > now()


async def test_the_right_password_during_the_wait_is_told_to_wait(client, db, tenant, tenant_headers):
    await make_target(db, tenant)
    await wrong(client, tenant_headers, "target@acme.com", settings.security.sign_in_attempts)

    answer = await client.post("/api/signin", json={"login": "target@acme.com", "password": "the-right-one"}, headers=tenant_headers)

    assert answer.status_code == 401
    assert answer.json()["code"] == "error.too-many-attempts"


async def test_a_wrong_password_during_the_wait_says_what_it_always_said(client, db, tenant, tenant_headers):
    """Whoever is guessing must not learn that they found an account, and the wait itself would tell them."""
    await make_target(db, tenant)
    await wrong(client, tenant_headers, "target@acme.com", settings.security.sign_in_attempts)

    answer = await client.post("/api/signin", json={"login": "target@acme.com", "password": "still-wrong"}, headers=tenant_headers)

    assert answer.status_code == 401
    assert answer.json()["code"] == "error.invalid-credentials"


async def test_a_login_that_names_nobody_answers_the_same_and_counts_nothing(client, db, tenant, tenant_headers):
    answer = await client.post("/api/signin", json={"login": "nobody@acme.com", "password": "whatever"}, headers=tenant_headers)

    assert answer.status_code == 401
    assert answer.json()["code"] == "error.invalid-credentials"


async def test_the_wait_passing_lets_the_account_back_in(client, db, tenant, tenant_headers):
    user = await make_target(db, tenant)
    await wrong(client, tenant_headers, "target@acme.com", settings.security.sign_in_attempts)

    user.sign_in_blocked_until = now() - timedelta(seconds=1)
    await db.commit()

    answer = await client.post("/api/signin", json={"login": "target@acme.com", "password": "the-right-one"}, headers=tenant_headers)

    assert answer.status_code == 200


async def test_signing_in_clears_what_the_wrong_ones_counted(client, db, tenant, tenant_headers):
    user = await make_target(db, tenant)
    await wrong(client, tenant_headers, "target@acme.com", settings.security.sign_in_attempts - 1)

    await client.post("/api/signin", json={"login": "target@acme.com", "password": "the-right-one"}, headers=tenant_headers)
    await db.refresh(user)

    assert user.failed_sign_ins == 0
    assert user.sign_in_blocked_until is None


async def test_the_wait_grows_with_every_wrong_password_past_the_ceiling(db, tenant):
    """Guessing at one account gets slower the longer it goes on, and the wait it earns has a ceiling of its own."""
    user = await make_target(db, tenant)
    waits = []

    for _ in range(settings.security.sign_in_attempts + 6):
        await auth_service.count_failure(db, user)
        waits.append((user.sign_in_blocked_until - now()).total_seconds() if user.sign_in_blocked_until else 0)

    assert waits[settings.security.sign_in_attempts - 2] == 0
    assert waits[settings.security.sign_in_attempts - 1] < waits[settings.security.sign_in_attempts]
    assert max(waits) <= settings.security.sign_in_cooldown_max


async def test_attempts_arriving_together_are_all_counted(client, db, tenant, tenant_headers):
    """Reading the count and writing it back loses one whenever two arrive at once, and that is attempts an attacker gets for free."""
    import asyncio

    user = await make_target(db, tenant)
    wrong = {"login": "target@acme.com", "password": "not-the-password"}

    await asyncio.gather(*[client.post("/api/signin", json=wrong, headers=tenant_headers) for _ in range(4)])
    await db.refresh(user)

    assert user.failed_sign_ins == 4


async def test_guesses_sent_together_never_let_the_right_one_slip_past_the_wait_the_others_started(db, tenant):
    """Every guess of a burst read the account before any of them counted, so the wait is asked again by the write that signs in."""
    user = await make_target(db, tenant)
    stale = await user_service.get(db, user.id)

    await db.execute(update(User).where(User.id == user.id).values(sign_in_blocked_until=now() + timedelta(minutes=5)))
    await db.commit()
    stale.sign_in_blocked_until = None

    with pytest.raises(AuthenticationError, match="too-many-attempts"):
        await auth_service.settle_sign_in(db, stale, "the-right-one")


async def test_a_wait_written_by_one_failure_is_never_shortened_by_another_counted_with_it(db, tenant):
    user = await make_target(db, tenant)
    later = now() + timedelta(hours=1)

    await db.execute(update(User).where(User.id == user.id).values(failed_sign_ins=settings.security.sign_in_attempts, sign_in_blocked_until=later))
    await db.commit()

    await auth_service.count_failure(db, user)
    await db.refresh(user)

    assert user.sign_in_blocked_until == later
