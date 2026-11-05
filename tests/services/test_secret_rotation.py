"""A key that cannot be replaced is a key that cannot leak, and this one can be replaced."""

import pytest

from helpers import security
from helpers.conflict_error import ConflictError
from helpers.security import decrypt, encrypt, key_from
from helpers.settings import settings
from helpers.validation_error import ValidationError
from services.rotation_service import rotation_service
from tests.factories import make_integration


def keyed(monkeypatch, *passphrases):
    from cryptography.fernet import MultiFernet

    monkeypatch.setattr(security, "fernet", MultiFernet([key_from(passphrase) for passphrase in passphrases]))


def test_a_secret_written_with_the_key_before_is_still_read(monkeypatch):
    """This is what makes a deploy with a new key not turn every stored secret into nothing."""
    keyed(monkeypatch, "the-old-one")
    stored = encrypt("sk_live_worth_money")

    keyed(monkeypatch, "the-new-one", "the-old-one")

    assert decrypt(stored) == "sk_live_worth_money"


def test_a_secret_is_written_with_the_first_key(monkeypatch):
    keyed(monkeypatch, "the-new-one", "the-old-one")
    stored = encrypt("sk_live_worth_money")

    keyed(monkeypatch, "the-new-one")

    assert decrypt(stored) == "sk_live_worth_money"


def test_a_key_that_opens_nothing_reads_as_a_secret_nobody_set(monkeypatch):
    keyed(monkeypatch, "the-old-one")
    stored = encrypt("sk_live_worth_money")

    keyed(monkeypatch, "a-key-that-was-never-used")

    assert decrypt(stored) is None


async def test_key_rotation_preserves_an_in_flight_social_authorization(db, tenant, social_login, monkeypatch):
    from enums.authentication_surface import AuthenticationSurface
    from enums.social_provider import SocialProvider
    from helpers.brand import of
    from services.social_login_service import social_login_service

    keyed(monkeypatch, "old-key")
    authorization = await social_login_service.start(db, of(tenant), SocialProvider.GOOGLE, AuthenticationSurface.SITE, "/account")
    verifier = decrypt(authorization.attempt.verifier_encrypted)

    keyed(monkeypatch, "new-key", "old-key")
    assert await rotation_service.rewrite(db) == 1

    keyed(monkeypatch, "new-key")
    await db.refresh(authorization.attempt)

    assert decrypt(authorization.attempt.verifier_encrypted) == verifier


async def test_rotating_writes_every_stored_secret_with_the_key_that_writes_now(db, tenant, monkeypatch):
    keyed(monkeypatch, "the-old-one")
    integration = await make_integration(db, tenant)
    integration.stripe_api_key_encrypted = encrypt("sk_live_worth_money")
    integration.stripe_webhook_secret_encrypted = encrypt("whsec_worth_money")
    await db.commit()

    keyed(monkeypatch, "the-new-one", "the-old-one")

    assert await rotation_service.rewrite(db) == 2

    keyed(monkeypatch, "the-new-one")
    await db.refresh(integration)

    assert decrypt(integration.stripe_api_key_encrypted) == "sk_live_worth_money"
    assert decrypt(integration.stripe_webhook_secret_encrypted) == "whsec_worth_money"


async def test_rotating_refuses_rather_than_writing_over_what_it_could_not_open(db, tenant, monkeypatch):
    """Rewriting an unreadable secret would replace it with nothing, and nobody would know until a gateway called."""
    keyed(monkeypatch, "a-key-nobody-configured")
    integration = await make_integration(db, tenant)
    integration.stripe_api_key_encrypted = encrypt("sk_live_worth_money")
    await db.commit()

    keyed(monkeypatch, "the-new-one")

    with pytest.raises(ValidationError) as refused:
        await rotation_service.rewrite(db)

    assert refused.value.code == "error.secret-unreadable"


async def test_rotation_refuses_to_overwrite_a_credential_updated_after_its_read(db, tenant, monkeypatch):
    from sqlalchemy import update

    from helpers.db import AsyncSessionLocal
    from models.integration import Integration

    integration = await make_integration(db, tenant, stripe_api_key_encrypted=encrypt("previous-secret"))
    integration_id = integration.id
    execute = db.execute
    changed = False

    async def concurrent_update(statement, *args, **kwargs):
        nonlocal changed

        result = await execute(statement, *args, **kwargs)

        if statement.is_select and "FROM integration" in str(statement) and not changed:
            changed = True

            async with AsyncSessionLocal() as concurrent:
                await concurrent.execute(update(Integration).where(Integration.id == integration_id).values(stripe_api_key_encrypted=encrypt("replacement-secret")))
                await concurrent.commit()

        return result

    monkeypatch.setattr(db, "execute", concurrent_update)

    with pytest.raises(ConflictError):
        await rotation_service.rewrite(db)

    await db.refresh(integration)

    assert decrypt(integration.stripe_api_key_encrypted) == "replacement-secret"


async def test_rotation_handles_multiple_pages_without_loading_unrelated_integration_metadata(db, tenant, monkeypatch):
    from services import rotation_service as rotation

    monkeypatch.setattr(rotation, "BATCH_SIZE", 1)
    populated = await make_integration(db, tenant, stripe_api_key_encrypted=encrypt("stored-secret"), meta={"description": "x" * 100_000})
    empty = await make_integration(db)

    assert await rotation_service.rewrite(db) == 1
    await db.refresh(populated)
    await db.refresh(empty)

    assert decrypt(populated.stripe_api_key_encrypted) == "stored-secret"
    assert empty.stripe_api_key_encrypted is None


async def test_an_unreadable_secret_rolls_back_secrets_already_rewritten(db, tenant, monkeypatch):
    from sqlalchemy import select

    from models.integration import Integration

    readable = await make_integration(db, tenant, stripe_api_key_encrypted=encrypt("readable-secret"))
    readable_id = readable.id
    previous = readable.stripe_api_key_encrypted
    await make_integration(db, stripe_api_key_encrypted="unreadable-secret")

    with pytest.raises(ValidationError):
        await rotation_service.rewrite(db)

    assert await db.scalar(select(Integration.stripe_api_key_encrypted).where(Integration.id == readable_id)) == previous


def test_every_environment_configures_at_least_one_key():
    assert len(settings.security.encryption_keys) >= 1


def test_the_rewrite_reads_the_schema_rather_than_a_list_somebody_keeps():
    """A model that grows a secret later is rewritten without anybody remembering to add it here."""
    import models.registry  # noqa: F401
    from helpers.database_base import Base

    carrying = {mapper.class_.__name__ for mapper in Base.registry.mappers if any(column.key.endswith("_encrypted") for column in mapper.columns)}

    assert {model.__name__ for model, _ in rotation_service.stored()} == carrying
    assert carrying


def test_every_stored_secret_of_a_model_is_rewritten_and_not_the_first_one():
    columns = dict(rotation_service.stored())[__import__("models.integration", fromlist=["Integration"]).Integration]

    assert len(columns) > 1
    assert all(name.endswith("_encrypted") for name in columns)
