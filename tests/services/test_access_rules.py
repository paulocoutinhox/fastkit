import pytest

from enums.user_role import UserRole
from models.user_group import UserGroup
from models.user_group_member import UserGroupMember
from services.all_of import AllOf
from services.any_of import AnyOf
from services.everyone import Everyone
from services.has_role import HasRole
from services.in_group import InGroup
from services.signed_in import SignedIn
from services.user_group_service import user_group_service
from tests.factories import save


async def join(db, user, code: str, active: bool = True) -> UserGroup:
    group = await save(db, UserGroup(code=code, name=code.title(), active=active, tenant_id=user.tenant_id))
    await save(db, UserGroupMember(group_id=group.id, user_id=user.id))

    return group


async def test_everyone_lets_in_a_visitor_with_no_session(db):
    assert await Everyone().admits(db, None)


async def test_a_signed_in_rule_lets_in_any_account_and_no_visitor(db, member):
    assert await SignedIn().admits(db, member)
    assert not await SignedIn().admits(db, None)


async def test_a_role_rule_reads_the_role_of_the_account(db, member, administrator):
    rule = HasRole(UserRole.ADMINISTRATOR)

    assert await rule.admits(db, administrator)
    assert not await rule.admits(db, member)
    assert not await rule.admits(db, None)


async def test_a_role_rule_naming_no_role_lets_nobody_in(db, administrator):
    assert not await HasRole().admits(db, administrator)


async def test_a_group_rule_lets_in_the_members_of_an_active_group_only(db, member, administrator):
    await join(db, member, "finance")
    await join(db, administrator, "finance", active=False)

    assert await InGroup("finance").admits(db, member)
    assert not await InGroup("finance").admits(db, administrator)
    assert not await InGroup("finance").admits(db, None)
    assert not await InGroup("sales").admits(db, member)


async def test_the_groups_of_an_account_are_never_asked_for_by_a_rule_that_names_none(db, member, monkeypatch):
    async def never(*arguments):
        raise AssertionError("a rule naming no group asked for the groups")

    monkeypatch.setattr(user_group_service, "codes_of", never)

    assert await AnyOf(HasRole(UserRole.NORMAL), SignedIn()).admits(db, member)


async def test_rules_combine_into_either_and_both(db, member, administrator):
    await join(db, member, "finance")

    either = AnyOf(HasRole(UserRole.ADMINISTRATOR), InGroup("finance"))
    both = AllOf(HasRole(UserRole.ADMINISTRATOR), InGroup("finance"))

    assert await either.admits(db, member)
    assert await either.admits(db, administrator)
    assert not await both.admits(db, member)
    assert not await both.admits(db, administrator)
    assert either.groups_named() == {"finance"}


async def test_a_combination_of_no_rule_lets_nobody_in_and_one_requiring_every_rule_of_nothing_is_refused(db, administrator):
    assert not await AnyOf().admits(db, administrator)

    with pytest.raises(ValueError):
        AllOf()
