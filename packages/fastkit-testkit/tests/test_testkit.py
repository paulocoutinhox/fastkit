from datetime import datetime, timezone

import pytest

from fastkit_testkit.asserts import (
    EnvelopeAssertionError,
    assert_error,
    assert_field_error,
    assert_success,
)
from fastkit_testkit.clock import FrozenClock
from fastkit_testkit.database import sqlite_url, managed_database
from fastkit_testkit.factories import Factory, Sequence
from fastkit_testkit.providers import FakeMailbox, RecordingHook


def test_frozen_clock():
    clock = FrozenClock(datetime(2026, 7, 14, tzinfo=timezone.utc))

    assert clock() == datetime(2026, 7, 14, tzinfo=timezone.utc)
    assert clock.now() == clock()

    clock.tick(60)
    assert clock().minute == 1

    clock.set(datetime(2030, 1, 1, tzinfo=timezone.utc))
    assert clock().year == 2030


def test_frozen_clock_default():
    assert FrozenClock()().year == 2026


def test_sequence():
    sequence = Sequence(start=5)

    assert sequence.next() == 5
    assert sequence.next() == 6


def test_factory_build():
    class UserFactory(Factory):
        defaults = {"email": lambda index: f"user{index}@acme.com", "role": "member"}

    factory = UserFactory()

    first = factory.build()
    second = factory.build(role="admin")

    assert first["email"] == "user1@acme.com"
    assert first["role"] == "member"
    assert second["email"] == "user2@acme.com"
    assert second["role"] == "admin"

    batch = factory.build_batch(3)
    assert len(batch) == 3


def test_assert_success():
    data = assert_success({"success": True, "data": {"id": 1}})

    assert data == {"id": 1}

    with pytest.raises(EnvelopeAssertionError):
        assert_success({"success": False, "message": {"code": "x"}})


def test_assert_error():
    assert_error(
        {"success": False, "message": {"code": "validation.failed"}},
        "validation.failed",
    )

    with pytest.raises(EnvelopeAssertionError, match="got success"):
        assert_error({"success": True})

    with pytest.raises(EnvelopeAssertionError, match="expected error code"):
        assert_error(
            {"success": False, "message": {"code": "other"}}, "validation.failed"
        )


def test_assert_field_error():
    envelope = {"success": False, "errors": [{"field": "email", "code": "x"}]}

    assert assert_field_error(envelope, "email")["code"] == "x"

    with pytest.raises(EnvelopeAssertionError, match="no field error"):
        assert_field_error(envelope, "name")


def test_recording_hook():
    hook = RecordingHook()

    assert hook.count == 0

    with pytest.raises(AssertionError, match="never called"):
        hook.last()


async def test_recording_hook_records():
    from fastkit_core.events.bus import Event

    hook = RecordingHook()
    await hook(Event(name="user.created", payload={"id": 1}))

    assert hook.count == 1
    assert hook.last() == {"id": 1}


def test_fake_mailbox():
    mailbox = FakeMailbox()
    mailbox.deliver(["a@b.c"], "Hi", "body")
    mailbox.deliver(["x@y.z"], "Yo", "body")

    assert len(mailbox.to("a@b.c")) == 1
    assert len(mailbox.messages) == 2

    mailbox.clear()
    assert mailbox.messages == []


def test_sqlite_url(tmp_path):
    assert sqlite_url(tmp_path).startswith("sqlite+aiosqlite:///")


async def test_managed_database_context(tmp_path):
    from fastkit_db.base import Base

    async with managed_database(Base.metadata, tmp_path) as database:
        assert database.dialect_name == "sqlite"
