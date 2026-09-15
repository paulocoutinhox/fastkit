import pytest

from enums.user import UserStatus
from helpers.auth import get_optional_user, load_user
from helpers.errors import AuthenticationError
from helpers.security import create_token


async def test_load_user_answers_the_account_behind_the_token(db, member):
    assert (await load_user(db, create_token(member.token, member.role, member.session_epoch))).id == member.id


async def test_load_user_refuses_a_broken_token(db):
    with pytest.raises(AuthenticationError) as error:
        await load_user(db, "not-a-token")

    assert error.value.code == "error.invalid-token"


async def test_load_user_refuses_a_token_of_an_account_that_is_gone(db, member):
    token = create_token(member.token, member.role, member.session_epoch)

    await db.delete(member)
    await db.commit()

    with pytest.raises(AuthenticationError) as error:
        await load_user(db, token)

    assert error.value.code == "error.invalid-token"


@pytest.mark.parametrize("status,code", [(UserStatus.BLOCKED, "error.account-blocked"), (UserStatus.PENDING, "error.account-pending")])
async def test_load_user_refuses_an_unusable_account(db, member, status, code):
    member.status = status
    await db.commit()

    with pytest.raises(AuthenticationError) as error:
        await load_user(db, create_token(member.token, member.role, member.session_epoch))

    assert error.value.code == code


async def test_the_optional_user_stays_none_without_credentials(db):
    assert await get_optional_user(db, None) is None
