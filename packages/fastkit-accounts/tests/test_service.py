import pytest

from fastkit_core.errors.exceptions import ConflictError, NotFoundError, ValidationError
from fastkit_accounts.models import User


async def test_global_tenant_identifier_uniqueness_is_enforced_at_db_level(service):
    from sqlalchemy.exc import IntegrityError

    from fastkit_accounts.models import LoginIdentifier

    user = await service.create_user(
        tenant_id=0, identifiers=[("email", "root@x.com")], is_root=True
    )

    async with service._database.session_factory() as session:
        session.add(
            LoginIdentifier(
                user_id=user.id,
                tenant_id=None,
                type="email",
                value="root@x.com",
                normalized_value="root@x.com",
            )
        )

        with pytest.raises(IntegrityError):
            await session.commit()


async def test_profile_mutators_reject_a_missing_user(service):
    with pytest.raises(NotFoundError):
        await service.update_profile(999999, display_name="Ghost")

    with pytest.raises(NotFoundError):
        await service.set_password_hash(999999, "hash")


async def test_create_user_with_identifiers(service):
    user = await service.create_user(
        tenant_id=1,
        identifiers=[("email", "Owner@Acme.com"), ("username", "Owner")],
        display_name="Owner",
        is_staff=True,
    )

    assert user.tenant_id == 1
    assert user.email == "owner@acme.com"
    assert user.username == "owner"
    assert user.is_staff is True
    assert len(user.identifiers) == 2
    assert user.identifiers[0].is_primary is True
    assert user.profile is not None


async def test_create_global_root_user(service):
    user = await service.create_user(
        tenant_id=0, identifiers=[("email", "root@platform.com")], is_root=True
    )

    assert user.tenant_id is None
    assert user.is_root is True


async def test_root_must_be_global(service):
    with pytest.raises(ConflictError, match="global tenant"):
        await service.create_user(
            tenant_id=5, identifiers=[("email", "x@y.com")], is_root=True
        )


async def test_duplicate_identifier_same_tenant_rejected(service):
    await service.create_user(tenant_id=1, identifiers=[("email", "dup@acme.com")])

    with pytest.raises(ConflictError, match="already exists"):
        await service.create_user(tenant_id=1, identifiers=[("email", "DUP@acme.com")])


async def test_duplicate_identifier_within_one_payload_is_a_conflict_not_a_500(service):
    with pytest.raises(ConflictError, match="already exists"):
        await service.create_user(
            tenant_id=1,
            identifiers=[("email", "twice@acme.com"), ("email", "twice@acme.com")],
        )


async def test_same_identifier_across_tenants_allowed(service):
    await service.create_user(tenant_id=1, identifiers=[("email", "same@acme.com")])
    other = await service.create_user(
        tenant_id=2, identifiers=[("email", "same@acme.com")]
    )

    assert other.tenant_id == 2


async def test_invalid_identifier_rejected(service):
    with pytest.raises(ValidationError):
        await service.create_user(tenant_id=1, identifiers=[("email", "not-valid")])


async def test_find_candidates_local_and_global(service):
    local = await service.create_user(
        tenant_id=1, identifiers=[("email", "user@acme.com")]
    )
    global_user = await service.create_user(
        tenant_id=0, identifiers=[("email", "user@acme.com")]
    )

    candidates = await service.find_candidates(
        requested_tenant_id=1, identifier_type="email", raw_value="user@acme.com"
    )
    ids = {candidate.id for candidate in candidates}

    assert local.id in ids
    assert global_user.id in ids


async def test_find_candidates_empty(service):
    assert (
        await service.find_candidates(
            requested_tenant_id=1, identifier_type="email", raw_value="ghost@acme.com"
        )
        == []
    )


async def test_create_user_with_phone_mirrors_field(service):
    user = await service.create_user(
        tenant_id=1,
        identifiers=[("phone", "+5511988887777"), ("cpf", "123.456.789-09")],
    )

    assert user.phone == "+5511988887777"


def test_user_full_name():
    assert User(first_name="Ada", last_name="Lovelace").full_name == "Ada Lovelace"
    assert User(display_name="Root").full_name == "Root"
    assert User().full_name == ""


def test_registry_and_service_expose_identifier_types():
    from fastkit_accounts.normalizers import default_registry
    from fastkit_accounts.service import AccountService

    types = default_registry().types()
    assert "email" in types and "phone" in types
    assert types == sorted(types)

    assert AccountService(database=None).identifier_types() == types


def test_user_display_label():
    assert User(display_name="Root").display_label() == "Root"
    assert (
        User(first_name="Ada", last_name="Lovelace").display_label() == "Ada Lovelace"
    )
    assert User(email="ada@acme.com").display_label() == "ada@acme.com"
    assert User(id=7).display_label() == "7"


async def test_get_user_and_identifiers(service):
    user = await service.create_user(
        tenant_id=1, identifiers=[("email", "u@acme.com"), ("phone", "+5511988887777")]
    )

    loaded = await service.get_user(user.id)
    assert loaded.id == user.id

    identifiers = await service.list_identifiers(user.id)
    assert {item.type for item in identifiers} == {"email", "phone"}


async def test_add_and_remove_identifier(service):
    user = await service.create_user(
        tenant_id=1, identifiers=[("email", "add@acme.com")]
    )

    added = await service.add_identifier(
        user.id, tenant_id=1, identifier_type="cpf", raw_value="123.456.789-09"
    )
    assert added.type == "cpf"
    assert added.normalized_value == "12345678909"

    identifiers = await service.list_identifiers(user.id)
    assert len(identifiers) == 2

    # a non-numeric id never reaches the integer PK lookup (no Postgres DataError, no 500)
    assert await service.remove_identifier(user.id, "not-a-number") is False
    # a numeric string id is coerced to the integer PK
    assert await service.remove_identifier(user.id, str(added.id)) is True
    assert await service.remove_identifier(user.id, added.id) is False


async def test_add_identifier_rejects_duplicate(service):
    from fastkit_core.errors.exceptions import ConflictError

    user = await service.create_user(
        tenant_id=1, identifiers=[("email", "dup2@acme.com")]
    )

    with pytest.raises(ConflictError, match="already exists"):
        await service.add_identifier(
            user.id, tenant_id=1, identifier_type="email", raw_value="dup2@acme.com"
        )


async def test_remove_identifier_rejects_other_owner(service):
    owner = await service.create_user(
        tenant_id=1, identifiers=[("email", "owner2@acme.com")]
    )
    other = await service.create_user(
        tenant_id=1, identifiers=[("email", "other2@acme.com")]
    )

    other_identifier = (await service.list_identifiers(other.id))[0]

    assert await service.remove_identifier(owner.id, other_identifier.id) is False


async def test_update_profile_and_avatar(service):
    from fastkit_accounts.models import UserProfile

    avatar_id = 4242
    user = await service.create_user(
        tenant_id=1, identifiers=[("email", "prof@acme.com")], display_name="Old"
    )

    updated = await service.update_profile(
        user.id,
        display_name="New",
        first_name="Ada",
        timezone="Europe/Lisbon",
        avatar_file_id=avatar_id,
    )

    assert updated.display_name == "New"
    assert updated.first_name == "Ada"
    assert updated.profile.avatar_file_id == avatar_id

    # a no-op update leaves the record untouched (every value is None)
    unchanged = await service.update_profile(user.id)
    assert unchanged.display_name == "New"

    # cover the branch that lazily creates a profile when one is missing
    async with service._database.session_factory() as session:
        await session.execute(
            UserProfile.__table__.delete().where(UserProfile.user_id == user.id)
        )
        await session.commit()

    new_avatar = 5252
    recreated = await service.update_profile(user.id, avatar_file_id=new_avatar)
    assert recreated.profile.avatar_file_id == new_avatar


async def test_set_password_hash(service):
    user = await service.create_user(
        tenant_id=1, identifiers=[("email", "pwd@acme.com")]
    )

    await service.set_password_hash(user.id, "new-hash")

    assert (await service.get_user(user.id)).password_hash == "new-hash"


async def test_consumer_can_add_a_custom_identifier_type(database):
    from fastkit_accounts.normalizers import _fail, default_registry
    from fastkit_accounts.service import AccountService

    class MembershipNumberNormalizer:
        type = "membership_number"

        def normalize(self, value: str) -> str:
            return value.strip().upper()

        def mask(self, value: str) -> str:
            return value

        def validate(self, value: str) -> None:
            if not value.strip():
                raise _fail("value", "validation.required")

    registry = default_registry()
    registry.register(MembershipNumberNormalizer())
    service = AccountService(database, registry)

    assert "membership_number" in service.identifier_types()

    user = await service.create_user(
        tenant_id=1, identifiers=[("membership_number", " mb-7 ")]
    )

    candidates = await service.find_candidates(
        requested_tenant_id=1, identifier_type="membership_number", raw_value="mb-7"
    )

    assert [candidate.id for candidate in candidates] == [user.id]
