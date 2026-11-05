import pytest
from sqlalchemy import update

from enums.authentication_surface import AuthenticationSurface
from helpers.authentication_error import AuthenticationError
from helpers.authentication_helper import AuthenticationHelper
from models.user import User
from services.user_service import user_service


async def test_a_stale_account_cannot_open_a_session_after_its_epoch_changed(db, tenant, member):
    await db.execute(update(User).where(User.id == member.id).values(session_epoch=User.session_epoch + 1).execution_options(synchronize_session=False))
    await db.commit()

    with pytest.raises(AuthenticationError, match="invalid-credentials"):
        await AuthenticationHelper.signed_in(db, member, AuthenticationSurface.SITE, tenant.id)


async def test_a_password_change_between_claiming_and_loading_the_account_refuses_the_session(db, tenant, member, monkeypatch):
    load = user_service.get

    async def changed_before_read(session, identifier):
        await session.execute(update(User).where(User.id == identifier).values(session_epoch=User.session_epoch + 1))
        await session.commit()

        return await load(session, identifier)

    monkeypatch.setattr(user_service, "get", changed_before_read)

    with pytest.raises(AuthenticationError, match="invalid-credentials"):
        await AuthenticationHelper.signed_in(db, member, AuthenticationSurface.SITE, tenant.id)
