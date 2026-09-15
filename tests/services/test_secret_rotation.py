"""A key that cannot be replaced is a key that cannot leak, and this one can be replaced."""

import pytest

from helpers import security
from helpers.errors import ValidationError
from helpers.security import decrypt, encrypt, key_from
from helpers.settings import settings
from services.rotation import rotation_service
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


def test_every_environment_configures_at_least_one_key():
    assert len(settings.security.encryption_keys) >= 1


def test_the_rewrite_reads_the_schema_rather_than_a_list_somebody_keeps():
    """A model that grows a secret later is rewritten without anybody remembering to add it here."""
    import models.registry  # noqa: F401
    from helpers.db import Base

    carrying = {mapper.class_.__name__ for mapper in Base.registry.mappers if any(column.key.endswith("_encrypted") for column in mapper.columns)}

    assert {model.__name__ for model, _ in rotation_service.stored()} == carrying
    assert carrying


def test_every_stored_secret_of_a_model_is_rewritten_and_not_the_first_one():
    columns = dict(rotation_service.stored())[__import__("models.integration", fromlist=["Integration"]).Integration]

    assert len(columns) > 1
    assert all(name.endswith("_encrypted") for name in columns)
