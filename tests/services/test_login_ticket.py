from datetime import timedelta

import pytest
from sqlalchemy import select

from enums.user_role import UserRole
from enums.user_status import UserStatus
from helpers.authentication_error import AuthenticationError
from helpers.dates import now
from models.login_ticket import LoginTicket
from services.login_ticket_service import login_ticket_service


async def test_an_admin_ticket_is_bound_to_the_browser_and_is_used_once(db, tenant, administrator):
    ticket = await login_ticket_service.create(db, tenant.id, administrator, "browser-proof")
    record = await db.scalar(select(LoginTicket))

    assert ticket != record.token_digest
    assert "browser-proof" != record.browser_digest

    with pytest.raises(AuthenticationError):
        await login_ticket_service.redeem(db, tenant.id, ticket, "another-browser")

    assert (await login_ticket_service.redeem(db, tenant.id, ticket, "browser-proof")).id == administrator.id

    with pytest.raises(AuthenticationError):
        await login_ticket_service.redeem(db, tenant.id, ticket, "browser-proof")


async def test_an_admin_ticket_does_not_cross_the_tenant_where_the_login_started(db, tenant, administrator):
    ticket = await login_ticket_service.create(db, tenant.id, administrator, "browser-proof")

    with pytest.raises(AuthenticationError):
        await login_ticket_service.redeem(db, None, ticket, "browser-proof")


async def test_an_expired_admin_ticket_cannot_open_a_session(db, tenant, administrator):
    ticket = await login_ticket_service.create(db, tenant.id, administrator, "browser-proof")
    record = await db.scalar(select(LoginTicket))
    record.expires_at = now() - timedelta(seconds=1)
    await db.commit()

    with pytest.raises(AuthenticationError):
        await login_ticket_service.redeem(db, tenant.id, ticket, "browser-proof")


@pytest.mark.parametrize("changes", [{"session_epoch": 1}, {"status": UserStatus.BLOCKED}, {"status": UserStatus.ERASED}, {"role": UserRole.NORMAL}])
async def test_an_admin_ticket_rechecks_the_account_before_opening_a_session(db, tenant, administrator, changes):
    ticket = await login_ticket_service.create(db, tenant.id, administrator, "browser-proof")

    for name, value in changes.items():
        setattr(administrator, name, value)

    await db.commit()

    with pytest.raises(AuthenticationError):
        await login_ticket_service.redeem(db, tenant.id, ticket, "browser-proof")


async def test_a_ticket_for_an_account_that_was_deleted_is_refused(db, tenant, administrator):
    ticket = await login_ticket_service.create(db, tenant.id, administrator, "browser-proof")
    await db.delete(administrator)
    await db.commit()

    with pytest.raises(AuthenticationError):
        await login_ticket_service.redeem(db, tenant.id, ticket, "browser-proof")
