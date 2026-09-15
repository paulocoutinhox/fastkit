"""Erasing an account replaces the person and keeps the transactions, which is what the law asks and what accounting needs."""

import pytest
from sqlalchemy import func, select

from enums.account import CreditTransactionType
from enums.upload import UploadPurpose
from enums.user import UserStatus
from helpers.dates import now
from helpers.storage import storage
from models.account import CreditTransaction
from models.commerce import UserProduct
from models.event import AppEvent
from models.user import User, UserAddress
from services.auth import auth_service
from tests.factories import make_address, make_product, make_stored_file


@pytest.fixture
async def lived(currency, db, tenant, member):
    """An account that owned, reported, told us where it lives and paid, so every kind of row is on the table."""
    product = await make_product(db, tenant)

    await make_address(db, member)

    db.add_all(
        [
            UserProduct(user_id=member.id, product_id=product.id, granted_at=now()),
            AppEvent(tenant_id=tenant.id, user_id=member.id, uuid="e-1", name="product_viewed", params={}, occurred_at=now()),
            CreditTransaction(user_id=member.id, currency_id=currency.id, type=CreditTransactionType.CREDIT, amount=10, balance_after=10, idempotency_key="k-1", meta={}),
        ]
    )
    await db.commit()

    return {"product": product}


async def count(db, model, user_id) -> int:
    return await db.scalar(select(func.count()).select_from(model).where(model.user_id == user_id))


async def test_the_account_is_erased_and_answers_no_content(client, member_headers, lived):
    assert (await client.delete("/api/account/me", headers=member_headers)).status_code == 204


async def test_nothing_of_the_person_is_left_on_the_row(client, db, member, member_headers, lived):
    member_id = member.id

    await client.delete("/api/account/me", headers=member_headers)

    db.expire_all()
    erased = await db.get(User, member_id)

    assert erased.status == UserStatus.ERASED
    assert erased.erased_at is not None
    assert erased.first_name is None and erased.last_name is None and erased.nickname is None
    assert erased.avatar is None and erased.notes is None and erased.meta == {}


async def test_no_identity_of_the_person_survives(client, db, member, member_headers, lived):
    before = {"username": member.username, "email": member.email}
    member_id = member.id

    await client.delete("/api/account/me", headers=member_headers)

    db.expire_all()
    erased = await db.get(User, member_id)

    assert erased.username != before["username"]
    assert erased.email != before["email"]
    assert erased.email.endswith("@erased.invalid")


async def test_the_identity_it_had_signs_nobody_in(client, db, member, tenant, member_headers, lived):
    login, tenant_id = member.email, tenant.id

    await client.delete("/api/account/me", headers=member_headers)
    db.expire_all()

    with pytest.raises(Exception):
        await auth_service.authenticate(db, tenant_id, login, "s3cret-password")


async def test_the_address_it_had_is_free_for_a_new_account(client, db, member, tenant, tenant_headers, member_headers, lived):
    login = member.email

    await client.delete("/api/account/me", headers=member_headers)

    response = await client.post("/api/signup", headers=tenant_headers, json={"email": login, "password": "outra-senha-boa"})

    assert response.status_code == 201


async def test_every_device_is_signed_out(client, member_headers, lived):
    await client.delete("/api/account/me", headers=member_headers)

    assert (await client.get("/api/account/me", headers=member_headers)).status_code == 401


async def test_what_the_person_did_is_gone(client, db, member, member_headers, lived):
    await client.delete("/api/account/me", headers=member_headers)

    assert await count(db, UserAddress, member.id) == 0
    assert await count(db, AppEvent, member.id) == 0


async def test_what_the_person_paid_is_kept(client, db, member, member_headers, lived):
    await client.delete("/api/account/me", headers=member_headers)

    assert await count(db, CreditTransaction, member.id) == 1
    assert await count(db, UserProduct, member.id) == 1


async def test_the_picture_leaves_the_storage(client, db, member, member_headers, lived):
    key = await make_stored_file(db, UploadPurpose.AVATAR, "images/user/avatar", "png")

    await storage.save(key, b"not really a picture", "image/png")

    member.avatar = key
    await db.commit()

    await client.delete("/api/account/me", headers=member_headers)

    assert await storage.read(key) is None


async def test_erasing_is_written_down(client, db, member, member_headers, lived):
    from models.system_log import SystemLog

    await client.delete("/api/account/me", headers=member_headers)

    entries = (await db.execute(select(SystemLog).where(SystemLog.category == "account"))).scalars().all()

    assert len(entries) == 1
    assert entries[0].user_id == member.id


async def test_two_accounts_erased_in_the_same_tenant_do_not_collide(client, db, tenant, tenant_headers, lived):
    from enums.user import UserRole
    from services.user import user_service

    one = await user_service.create(db, {"email": "one@acme.com", "password": "s3cret-password", "role": UserRole.NORMAL, "status": UserStatus.ACTIVE, "tenant_id": tenant.id})
    two = await user_service.create(db, {"email": "two@acme.com", "password": "s3cret-password", "role": UserRole.NORMAL, "status": UserStatus.ACTIVE, "tenant_id": tenant.id})

    one_id, two_id = one.id, two.id

    await user_service.erase(db, one)
    await user_service.erase(db, two)

    db.expire_all()

    assert (await db.get(User, one_id)).email != (await db.get(User, two_id)).email


async def test_a_session_resolved_against_an_erased_account_is_refused(client, db, member, lived):
    """The row keeps a drawn token, and answering to it would hand back what was erased."""
    from helpers.security import create_token

    await client.delete("/api/account/me", headers={"Authorization": f"Bearer {create_token(member.token, member.role, member.session_epoch)}"})

    db.expire_all()
    erased = await db.scalar(select(User.token).where(User.status == UserStatus.ERASED))

    response = await client.get("/api/account/me", headers={"Authorization": f"Bearer {create_token(erased, 'normal', 0)}"})

    assert response.status_code == 401
